import asyncio
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DISTRICTS = json.loads((ROOT / "data/districts.json").read_text(encoding="utf-8"))
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MET_NORWAY_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
USER_AGENT = "KisanMitra/1.0 (hackathon project)"
CACHE_TTL = 3 * 60 * 60
logger = logging.getLogger(__name__)

# Values are (successful-fetch timestamp, forecast). Cached/sample responses
# are never written back as a live successful fetch.
_cache = {}
_last_diagnostics = {}


def district_for(value):
    item = next((d for d in DISTRICTS if d["id"] == value or d["name"]["en"].lower() == value.lower()), None)
    if not item:
        raise ValueError("Unknown district")
    return item


def _flags(daily):
    flags = []
    if any((x.get("rain") or 0) >= 25 or (x.get("rain_probability") or 0) >= 80 for x in daily):
        flags.append("heavy_rain")
    if any((x.get("rain_probability") or 0) >= 60 for x in daily[:2]):
        flags.append("rain_soon")
    known_rain = [x["rain"] for x in daily if x.get("rain") is not None]
    if len(known_rain) == len(daily) and sum(known_rain) < 5:
        flags.append("dry_spell")
    if any(x.get("max") is not None and x["max"] >= 40 for x in daily):
        flags.append("heat")
    if any(x.get("wind") is not None and x["wind"] >= 25 for x in daily):
        flags.append("wind_high")
    return flags


def _open_meteo_daily(raw):
    d = raw["daily"]
    return [
        {
            "date": d["time"][i],
            "max": d["temperature_2m_max"][i],
            "min": d["temperature_2m_min"][i],
            "rain": d["precipitation_sum"][i],
            "rain_probability": d["precipitation_probability_max"][i],
            "wind": d["wind_speed_10m_max"][i],
        }
        for i in range(min(7, len(d["time"])))
    ]


def _met_norway_forecast(raw):
    """Convert MET Norway's hourly/interval forecast to the app's daily shape."""
    series = raw.get("properties", {}).get("timeseries") or []
    if not series:
        raise ValueError("MET Norway response contains no forecast timeseries")

    local_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(timezone.utc)
    today = now.astimezone(local_tz).date()
    days = [today + timedelta(days=i) for i in range(7)]
    grouped = {day.isoformat(): [] for day in days}
    parsed = []
    for item in series:
        try:
            timestamp = datetime.fromisoformat(item["time"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            instant = item.get("data", {}).get("instant", {}).get("details", {})
            interval = item.get("data", {})
            precipitation = None
            # Prefer the one-hour interval. Longer intervals overlap and should
            # only be used when the API omits the shorter interval.
            for period in ("next_1_hours", "next_6_hours", "next_12_hours"):
                details = interval.get(period, {}).get("details", {})
                if details.get("precipitation_amount") is not None:
                    precipitation = details["precipitation_amount"]
                    break
            local_date = timestamp.astimezone(local_tz).date().isoformat()
            record = {
                "time": timestamp,
                "temperature": instant.get("air_temperature"),
                "humidity": instant.get("relative_humidity"),
                "wind": instant.get("wind_speed"),
                "rain": precipitation,
            }
            parsed.append(record)
            if local_date in grouped:
                grouped[local_date].append(record)
        except (KeyError, TypeError, ValueError):
            continue

    if not parsed:
        raise ValueError("MET Norway response has no usable forecast values")
    closest = min(parsed, key=lambda item: abs((item["time"] - now).total_seconds()))
    daily = []
    for day in days:
        records = grouped[day.isoformat()]
        temperatures = [r["temperature"] for r in records if r["temperature"] is not None]
        winds = [r["wind"] for r in records if r["wind"] is not None]
        rain_values = [r["rain"] for r in records if r["rain"] is not None]
        daily.append({
            "date": day.isoformat(),
            "max": max(temperatures) if temperatures else None,
            "min": min(temperatures) if temperatures else None,
            "rain": round(sum(rain_values), 1) if rain_values else None,
            # MET Norway's compact endpoint does not provide precipitation
            # probability, so leave it unknown instead of inventing a value.
            "rain_probability": None,
            "wind": round(max(winds), 1) if winds else None,
        })
    current = {
        "temperature_2m": closest["temperature"],
        "relative_humidity_2m": closest["humidity"],
        "precipitation": closest["rain"],
    }
    return {"current": current, "daily": daily, "flags": _flags(daily), "source": "met-norway"}


def _sample_forecast(district):
    """Deterministic, clearly labelled, plausible sample for UI continuity."""
    today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30))).date()
    seed = sum(ord(char) for char in district["id"]) % 5
    base = 29 + seed
    probabilities = [10, 15, 20, 35, 25, 15, 10]
    rain_values = [0, 0, 0.2, 1.0, 0.5, 0, 0]
    daily = []
    for i in range(7):
        daily.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "max": base + (1 if i in (1, 2) else 0),
            "min": max(15, base - 10 + (i % 2)),
            "rain": rain_values[i],
            "rain_probability": probabilities[i],
            "wind": round(9 + ((seed + i * 3) % 8) + 0.4, 1),
        })
    current = {
        "temperature_2m": daily[0]["min"] + 5,
        "relative_humidity_2m": 58 + seed,
        "precipitation": 0,
    }
    return {"current": current, "daily": daily, "flags": _flags(daily), "source": "sample"}


async def _fetch_open_meteo(district, diagnostics):
    params = {
        "latitude": district["latitude"],
        "longitude": district["longitude"],
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "timezone": "Asia/Kolkata",
        "forecast_days": 7,
    }
    attempts = []
    for attempt in range(3):
        response = None
        try:
            async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
                response = await client.get(OPEN_METEO_URL, params=params)
                response.raise_for_status()
                raw = response.json()
            daily = _open_meteo_daily(raw)
            if len(daily) < 7:
                raise ValueError("Open-Meteo returned fewer than seven forecast days")
            result = {"current": raw.get("current", {}), "daily": daily, "flags": _flags(daily), "source": "Open-Meteo"}
            diagnostics["Open-Meteo"] = {"status": "ok", "attempts": attempt + 1}
            return result
        except Exception as exc:
            error_response = getattr(exc, "response", None) or response
            status = getattr(error_response, "status_code", None)
            body = (getattr(error_response, "text", "") or "")[:200]
            attempt_error = {
                "http_status": status,
                "response_text": body,
                "exception_type": type(exc).__name__,
            }
            attempts.append(attempt_error)
            logger.warning(
                "Open-Meteo request failed (attempt %s/3): HTTP status=%s response_text=%r exception_type=%s",
                attempt + 1, status, body, type(exc).__name__,
            )
            if attempt < 2:
                await asyncio.sleep(0.35 * (attempt + 1))
    diagnostics["Open-Meteo"] = {"status": "error", "attempts": attempts}
    return None


async def _fetch_met_norway(district, diagnostics):
    params = {"lat": district["latitude"], "lon": district["longitude"]}
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(MET_NORWAY_URL, params=params)
            response.raise_for_status()
            raw = response.json()
        result = _met_norway_forecast(raw)
        diagnostics["MET Norway"] = {"status": "ok"}
        return result
    except Exception as exc:
        error_response = getattr(exc, "response", None) or locals().get("response")
        status = getattr(error_response, "status_code", None)
        body = (getattr(error_response, "text", "") or "")[:200]
        diagnostics["MET Norway"] = {
            "status": "error",
            "http_status": status,
            "response_text": body,
            "exception_type": type(exc).__name__,
        }
        logger.warning(
            "MET Norway request failed: HTTP status=%s response_text=%r exception_type=%s",
            status, body, type(exc).__name__,
        )
        return None


async def get_weather(district, *, force_refresh=False):
    key = district["id"]
    if not force_refresh and key in _cache and time.time() - _cache[key][0] < CACHE_TTL:
        result = dict(_cache[key][1])
        result["source"] = "cached"
        _last_diagnostics[key] = {"Open-Meteo": {"status": "not_checked_cache"}, "MET Norway": {"status": "not_checked_cache"}, "result": "cached"}
        return result

    diagnostics = {"Open-Meteo": {"status": "not_checked"}, "MET Norway": {"status": "not_checked"}}
    result = await _fetch_open_meteo(district, diagnostics)
    if result is None:
        result = await _fetch_met_norway(district, diagnostics)
    if result is not None:
        _cache[key] = (time.time(), result)
        _last_diagnostics[key] = diagnostics
        return result

    if key in _cache:
        cached = dict(_cache[key][1])
        cached["source"] = "cached"
        diagnostics["result"] = "cached"
        _last_diagnostics[key] = diagnostics
        return cached

    sample = _sample_forecast(district)
    diagnostics["result"] = "sample"
    _last_diagnostics[key] = diagnostics
    return sample


async def debug_weather(district):
    """Force a provider check and return safe, key-free diagnostics."""
    result = await get_weather(district, force_refresh=True)
    return {
        "district": district["id"],
        "source": result["source"],
        "providers": _last_diagnostics.get(district["id"], {}),
    }
