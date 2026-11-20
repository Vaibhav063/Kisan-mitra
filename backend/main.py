import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.ai import _fallback_ask, fallback_advice, generate
from services.crop_doctor import diagnose as diagnose_crop, debug_gemini, failure_result
from services.mandi import CROPS, get_mandi
from services.weather import DISTRICTS, _sample_forecast, debug_weather, district_for, get_weather

load_dotenv(Path(__file__).parent / ".env")
logger = logging.getLogger(__name__)
app = FastAPI(title="Kisan Mitra API", version="1.0.0")

allowed_origins = [
    item.strip().rstrip("/")
    for item in os.getenv("ALLOWED_ORIGIN", "http://localhost:5173").split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

hits = defaultdict(deque)
diagnose_hits = defaultdict(deque)
ADVICE_CACHE_TTL_SECONDS = 30 * 60
advice_cache = {}


@app.middleware("http")
async def rate_limit(request, call_next):
    host = request.client.host if request.client else "unknown"
    bucket = hits[host]
    now = time.time()
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= 30:
        return JSONResponse({"detail": "Too many requests. Please wait a minute and try again."}, status_code=429)
    bucket.append(now)
    return await call_next(request)


class AdviceRequest(BaseModel):
    district: str
    crop: str
    language: str = Field(pattern="^(mr|hi|en)$")


class AskRequest(AdviceRequest):
    question: str = Field(min_length=1, max_length=1000)


MAX_DIAGNOSIS_IMAGE_BYTES = 4 * 1024 * 1024
IMAGE_TYPES = {
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".webp": ("image/webp", b"RIFF"),
}


async def _safe_context(district, crop):
    weather_result, mandi_result = await asyncio.gather(
        get_weather(district),
        get_mandi(district, crop),
        return_exceptions=True,
    )
    if isinstance(weather_result, Exception):
        logger.warning("Weather context unavailable: exception_type=%s", type(weather_result).__name__)
        weather_result = _sample_forecast(district)
    if isinstance(mandi_result, Exception):
        logger.warning("Mandi context unavailable: exception_type=%s", type(mandi_result).__name__)
        mandi_result = {"markets": [], "best_market": None, "source": "sample"}
    return weather_result, mandi_result


def _scrub_secrets(value):
    secrets = [os.getenv(name, "").strip() for name in ("GEMINI_API_KEY", "DATA_GOV_API_KEY")]
    secrets = [secret for secret in secrets if secret]
    if isinstance(value, dict):
        return {key: _scrub_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_secrets(item) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
    return value


def _safe_advice(weather, mandi, language):
    try:
        return fallback_advice(weather, mandi, language)
    except Exception:
        return {
            "headline": "Check your crop carefully today",
            "actions": [{"type": "wait", "text": "Check local conditions before field work.", "urgency": "low"}],
            "explanation": "Live advice is temporarily unavailable. Please try again shortly.",
            "alerts": [],
            "weather_flags": weather.get("flags", []),
            "best_market": mandi.get("best_market"),
            "source_notes": "Basic fallback advice.",
        }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/districts")
async def districts():
    return DISTRICTS


@app.get("/api/weather")
async def weather(district: str):
    try:
        selected = district_for(district)
    except ValueError as exc:
        raise HTTPException(400, "Unknown district. Choose a district from the list.") from exc
    try:
        return await get_weather(selected)
    except Exception as exc:
        logger.warning("Weather endpoint fallback: exception_type=%s", type(exc).__name__)
        return _sample_forecast(selected)


@app.get("/api/debug/weather")
async def weather_debug(district: str):
    try:
        selected = district_for(district)
    except ValueError as exc:
        raise HTTPException(400, "Unknown district. Choose a district from the list.") from exc
    try:
        return _scrub_secrets(await debug_weather(selected))
    except Exception as exc:
        logger.warning("Weather diagnostics failed: exception_type=%s", type(exc).__name__)
        return {"district": selected["id"], "source": "sample", "providers": {"error": {"exception_type": type(exc).__name__}}}


@app.get("/api/mandi")
async def mandi(district: str, crop: str):
    try:
        selected = district_for(district)
    except ValueError as exc:
        raise HTTPException(400, "Unknown district. Choose a district from the list.") from exc
    if crop.lower() not in CROPS:
        raise HTTPException(400, "Unknown crop. Choose a supported crop.")
    try:
        return await get_mandi(selected, crop)
    except Exception as exc:
        logger.warning("Mandi endpoint fallback: exception_type=%s", type(exc).__name__)
        return {"markets": [], "best_market": None, "source": "sample", "message": "Market prices are temporarily unavailable."}


@app.post("/api/advice")
async def advice(body: AdviceRequest):
    try:
        selected = district_for(body.district)
    except ValueError as exc:
        raise HTTPException(400, "Unknown district. Choose a district from the list.") from exc
    if body.crop.lower() not in CROPS:
        raise HTTPException(400, "Unknown crop. Choose a supported crop.")

    cache_key = (selected["id"], body.crop.lower(), body.language)
    cached = advice_cache.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < ADVICE_CACHE_TTL_SECONDS:
        return deepcopy(cached[1])

    weather_data, mandi_data = await _safe_context(selected, body.crop)
    try:
        response = await generate("advice", selected, body.crop, body.language, weather_data, mandi_data)
        if not isinstance(response, dict):
            raise TypeError("Advice service returned an invalid response")
    except Exception as exc:
        logger.warning("Advice endpoint fallback: exception_type=%s", type(exc).__name__)
        response = _safe_advice(weather_data, mandi_data, body.language)
    advice_cache[cache_key] = (time.time(), deepcopy(response))
    return response


@app.post("/api/ask")
async def ask(body: AskRequest):
    try:
        selected = district_for(body.district)
    except ValueError as exc:
        raise HTTPException(400, "Unknown district. Choose a district from the list.") from exc
    if body.crop.lower() not in CROPS:
        raise HTTPException(400, "Unknown crop. Choose a supported crop.")
    weather_data, mandi_data = await _safe_context(selected, body.crop)
    try:
        response = await generate("ask", selected, body.crop, body.language, weather_data, mandi_data, body.question)
        if not isinstance(response, dict):
            raise TypeError("Ask service returned an invalid response")
        return response
    except Exception as exc:
        logger.warning("Ask endpoint fallback: exception_type=%s", type(exc).__name__)
        try:
            return _fallback_ask(body.question, weather_data, mandi_data, body.language)
        except Exception:
            message = {
                "mr": "सल्ला सध्या उपलब्ध नाही. कृपया पुन्हा प्रयत्न करा.",
                "hi": "सलाह अभी उपलब्ध नहीं है। कृपया फिर कोशिश करें।",
                "en": "Advice is temporarily unavailable. Please try again.",
            }[body.language]
            return {"answer": message, "reasons": [], "steps": [], "alerts": [], "basic_advice": True}


@app.post("/api/diagnose")
async def diagnose_endpoint(
    request: Request,
    image: UploadFile = File(...),
    crop: str = Form(...),
    district: str = Form(...),
    language: str = Form(...),
):
    now = time.time()
    host = request.client.host if request and request.client else "unknown"
    bucket = diagnose_hits[host]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= 10:
        raise HTTPException(429, "Too many crop diagnosis requests; try again in a minute")
    if language not in {"mr", "hi", "en"}:
        raise HTTPException(422, "language must be mr, hi or en")
    if not crop.strip():
        raise HTTPException(422, "crop is required")
    try:
        selected_district = district_for(district)
    except ValueError as exc:
        raise HTTPException(400, "Unknown district") from exc
    suffix = Path(image.filename or "").suffix.lower()
    accepted = IMAGE_TYPES.get(suffix)
    if not accepted or image.content_type != accepted[0]:
        raise HTTPException(415, "Upload a JPG, PNG or WEBP image")
    data = await image.read(MAX_DIAGNOSIS_IMAGE_BYTES + 1)
    await image.close()
    if len(data) > MAX_DIAGNOSIS_IMAGE_BYTES:
        raise HTTPException(413, "Image must be 4 MB or smaller")
    valid_signature = data.startswith(accepted[1])
    if suffix == ".webp":
        valid_signature = valid_signature and data[8:12] == b"WEBP"
    if not valid_signature:
        raise HTTPException(415, "The image contents do not match its file type")
    bucket.append(now)
    try:
        return await diagnose_crop(data, accepted[0], crop.strip(), selected_district, language)
    except Exception as exc:
        logger.warning("Crop diagnosis fallback: exception_type=%s", type(exc).__name__)
        return failure_result(language)


@app.get("/api/debug/gemini")
async def gemini_debug():
    try:
        return _scrub_secrets(await debug_gemini())
    except Exception as exc:
        logger.warning("Gemini diagnostics failed: exception_type=%s", type(exc).__name__)
        model = os.getenv("GEMINI_MODEL", "configured model")
        return {
            "model": model,
            "text_ok": False,
            "image_ok": False,
            "error": {"exception_type": type(exc).__name__, "message": "Gemini diagnostics could not complete."},
        }
