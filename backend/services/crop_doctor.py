import asyncio
import json
import logging
import os
import re

from google import genai
from google.genai import types


logger = logging.getLogger(__name__)
DEFAULT_MODEL = "gemini-3.8-flash"
FLASH_IMAGE_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash-lite")
LANGUAGES = {"mr": "Marathi", "hi": "Hindi", "en": "English"}
_MODEL_CACHE = {}

SYSTEM_PROMPT = """You are Crop Doctor, a careful visual crop-health assistant for farmers in India. Examine the supplied image closely. Reply only in the selected language using simple everyday farmer-friendly words. Return ONLY a JSON object with exactly these fields: plant_visible (boolean), crop_guess (short string, or unknown), possible_issue (specific issue name; if healthy say the plant looks healthy), confidence (low|medium|high), severity (low|medium|high), symptoms_seen (2-4 brief observations grounded only in visible pixels), likely_causes (1-3 plausible causes, labelled uncertain), what_to_do (3-5 practical steps), prevention_tip (one useful tip), see_officer_if (clear guidance). This is a possible visual diagnosis, never a certain diagnosis. Describe specific visible signs such as spots, discoloration, holes, curling, wilting, residue, or healthy leaves; do not infer symptoms not visible. If no plant is visible, set plant_visible=false, ask for a clearer photo of one crop leaf, and do not claim a crop disease. If the leaf looks healthy, say no clear problem is visible and focus on prevention. Never recommend pesticide or chemical dosages or prescribe a chemical. Recommend the local Krishi Vigyan Kendra (KVK) or agriculture officer for treatment. Keep the answer focused and readable."""

FAILURE_COPY = {
    "en": {
        "error_message": "The AI service is not available right now. Please try again in a minute.",
        "general_tips": ["Check both sides of a few leaves.", "Keep the crop watered as needed and remove badly damaged leaves if practical.", "Inspect the crop regularly for changes."],
        "see_officer_if": "For treatment, or if the problem spreads, contact your local Krishi Vigyan Kendra or agriculture officer.",
    },
    "mr": {
        "error_message": "AI सेवा सध्या उपलब्ध नाही. कृपया एका मिनिटाने पुन्हा प्रयत्न करा.",
        "general_tips": ["काही पानांच्या दोन्ही बाजू तपासा.", "गरजेनुसार पाणी द्या आणि शक्य असल्यास खूप खराब पाने काढा.", "पिकातील बदलांसाठी नियमित पाहणी करा."],
        "see_officer_if": "उपचारासाठी किंवा त्रास पसरल्यास स्थानिक कृषी विज्ञान केंद्र किंवा कृषी अधिकाऱ्यांशी संपर्क करा.",
    },
    "hi": {
        "error_message": "AI सेवा अभी उपलब्ध नहीं है। कृपया एक मिनट बाद फिर कोशिश करें।",
        "general_tips": ["कुछ पत्तियों के दोनों तरफ देखें।", "ज़रूरत के अनुसार पानी दें और हो सके तो बहुत खराब पत्तियाँ हटा दें।", "फसल में बदलाव के लिए नियमित जाँच करें।"],
        "see_officer_if": "इलाज के लिए, या समस्या फैलने पर, स्थानीय कृषि विज्ञान केंद्र या कृषि अधिकारी से संपर्क करें।",
    },
}


class GeminiResponseError(RuntimeError):
    pass


def _error_summary(error, key=""):
    response = getattr(error, "response", None)
    status = getattr(error, "status_code", None) or getattr(response, "status_code", None)
    message = str(error)
    if key:
        message = message.replace(key, "[REDACTED]")
    return {"exception_type": type(error).__name__, "http_status": status, "message": message[:300]}


def _log_failure(feature, error, key=""):
    summary = _error_summary(error, key)
    logger.error(
        "Gemini %s failed: exception_type=%s http_status=%s message=%s",
        feature, summary["exception_type"], summary["http_status"], summary["message"],
    )
    return summary


def _model_name(model):
    return str(getattr(model, "name", "")).removeprefix("models/")


def _list_models(client):
    return list(client.models.list())


def _supports_generate(model):
    actions = getattr(model, "supported_actions", None) or getattr(model, "supported_generation_methods", None) or []
    return not actions or any("generatecontent" in str(action).lower() for action in actions)


async def _resolve_model(client, configured):
    cached = _MODEL_CACHE.get(configured)
    if cached:
        return cached[0], cached[1], None
    try:
        models = await asyncio.to_thread(_list_models, client)
        by_name = {_model_name(model): model for model in models if _model_name(model)}
        configured_name = configured.removeprefix("models/")
        if configured_name in by_name and _supports_generate(by_name[configured_name]):
            chosen = configured_name
        else:
            chosen = next((name for name in FLASH_IMAGE_MODELS if name in by_name and _supports_generate(by_name[name])), None)
            if not chosen:
                raise ValueError("No listed Gemini Flash model with generateContent support was found")
        candidates = [name for name in FLASH_IMAGE_MODELS if name in by_name and _supports_generate(by_name[name])]
        _MODEL_CACHE[configured] = (chosen, candidates)
        return chosen, candidates, None
    except Exception as exc:
        # Keep the configured model so the actual call can produce the useful
        # auth/model error; the route will return an honest failure if it fails.
        return configured.removeprefix("models/"), list(FLASH_IMAGE_MODELS), exc


def _response_text(response):
    feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(feedback, "block_reason", None) if feedback else None
    if block_reason and str(block_reason).lower() not in {"blockreason.unspecified", "unspecified", "0"}:
        raise GeminiResponseError(f"Gemini safety block: {block_reason}")
    candidates = getattr(response, "candidates", None)
    if candidates is not None and len(candidates) == 0:
        raise GeminiResponseError("Gemini returned no candidates")
    if candidates:
        finish = getattr(candidates[0], "finish_reason", None)
        finish_name = str(getattr(finish, "name", finish) or "").upper()
        if any(marker in finish_name for marker in ("SAFETY", "BLOCK", "RECITATION", "PROHIBITED")):
            raise GeminiResponseError(f"Gemini response blocked: {finish_name}")
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise GeminiResponseError("Gemini returned an empty response")
    return text.strip()


def _strip_fence(text):
    text = (text or "").strip()
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()


def _parse_result(text):
    data = json.loads(_strip_fence(text))
    if not isinstance(data, dict):
        raise ValueError("Gemini result is not a JSON object")
    if not isinstance(data.get("plant_visible"), bool):
        raise ValueError("Missing boolean plant_visible")
    if not isinstance(data.get("crop_guess"), str) or not data["crop_guess"].strip():
        raise ValueError("Missing crop_guess")
    if not isinstance(data.get("possible_issue"), str) or not data["possible_issue"].strip():
        raise ValueError("Missing possible_issue")
    for field in ("confidence", "severity"):
        if data.get(field) not in {"low", "medium", "high"}:
            raise ValueError(f"Invalid {field}")
    for field, low, high in (("symptoms_seen", 2, 4), ("likely_causes", 1, 3), ("what_to_do", 3, 5)):
        values = data.get(field)
        if not isinstance(values, list) or not low <= len(values) <= high or not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError(f"Invalid {field}")
    for field in ("prevention_tip", "see_officer_if"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"Missing {field}")
    return {
        "service_available": True,
        "plant_visible": data["plant_visible"],
        "crop_guess": data["crop_guess"].strip(),
        "possible_issue": data["possible_issue"].strip(),
        "confidence": data["confidence"],
        "severity": data["severity"],
        "symptoms_seen": [value.strip() for value in data["symptoms_seen"]],
        "likely_causes": [value.strip() for value in data["likely_causes"]],
        "what_to_do": [value.strip() for value in data["what_to_do"]],
        "prevention_tip": data["prevention_tip"].strip(),
        "see_officer_if": data["see_officer_if"].strip(),
    }


def failure_result(language, error=None, key=""):
    lang = language if language in FAILURE_COPY else "en"
    result = dict(FAILURE_COPY[lang])
    result["service_available"] = False
    if error is not None:
        result["error_summary"] = _log_failure("diagnose", error, key)
    return result


def _generate_content(client, model, prompt, image_bytes=None, mime_type=None, json_output=True):
    parts = [prompt]
    if image_bytes is not None:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    config = {"temperature": 0.2}
    if json_output:
        config["response_mime_type"] = "application/json"
    response = client.models.generate_content(model=model, contents=parts, config=config)
    return _response_text(response)


async def diagnose(image_bytes, mime_type, crop, district, language):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return failure_result(language, RuntimeError("GEMINI_API_KEY is not configured"))
    configured = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        client = genai.Client(api_key=key)
        model, candidates, listing_error = await _resolve_model(client, configured)
        prompt = (
            SYSTEM_PROMPT
            + f"\nSelected response language: {LANGUAGES.get(language, 'English')}"
            + f"\nFarmer-selected crop: {crop}"
            + f"\nDistrict: {district['name']['en']}"
            + "\nDescribe concrete details visible in this image; avoid generic guesses."
        )
        last_error = None
        for model_try in [model] + [name for name in candidates if name != model][:1]:
            try:
                raw = await asyncio.to_thread(_generate_content, client, model_try, prompt, image_bytes, mime_type, True)
                for json_try in range(2):
                    try:
                        return _parse_result(raw)
                    except (json.JSONDecodeError, ValueError) as parse_error:
                        if json_try:
                            raise parse_error
                        correction = (
                            "Your previous response was not valid JSON matching the required schema. "
                            "Return only one valid JSON object with every required field, using the same image."
                        )
                        raw = await asyncio.to_thread(_generate_content, client, model_try, prompt + "\n" + correction, image_bytes, mime_type, True)
            except Exception as exc:
                last_error = exc
                text = str(exc).lower()
                is_model_or_image_error = any(token in text for token in ("model", "image", "modality", "not found", "not supported", "unsupported"))
                if model_try == model and len(candidates) > 1 and is_model_or_image_error:
                    continue
                break
        return failure_result(language, last_error or listing_error or RuntimeError("No usable Gemini response"), key)
    except Exception as exc:
        return failure_result(language, exc, key)


async def debug_gemini():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    configured = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if not key:
        error = RuntimeError("GEMINI_API_KEY is not configured")
        summary = _error_summary(error)
        _log_failure("debug", error)
        return {"model": configured, "text_ok": False, "image_ok": False, "error": {"text": summary, "image": summary}}
    client = genai.Client(api_key=key)
    model, candidates, listing_error = await _resolve_model(client, configured)
    errors = {"text": None, "image": None}
    text_ok = image_ok = False
    try:
        text = await asyncio.to_thread(_generate_content, client, model, "Reply with the single word OK.", None, None, False)
        text_ok = bool(text.strip())
    except Exception as exc:
        errors["text"] = _log_failure("debug text probe", exc, key)
    # A tiny valid 1x1 PNG tests inline image input without writing an image.
    tiny_png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082")
    try:
        text = await asyncio.to_thread(_generate_content, client, model, "Say whether this tiny image is visible; answer briefly.", tiny_png, "image/png", False)
        image_ok = bool(text.strip())
    except Exception as exc:
        errors["image"] = _log_failure("debug image probe", exc, key)
    if listing_error and not text_ok and not image_ok:
        errors["model_list"] = _error_summary(listing_error, key)
    return {"model": model, "configured_model": configured, "text_ok": text_ok, "image_ok": image_ok, "error": errors}
