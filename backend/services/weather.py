import json, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
DISTRICTS = json.loads((ROOT / "data/districts.json").read_text(encoding="utf-8"))
_cache = {}

def district_for(value):
    item = next((d for d in DISTRICTS if d["id"] == value or d["name"]["en"].lower() == value.lower()), None)
    if not item: raise ValueError("Unknown district")
    return item

async def get_weather(district):
    key = district["id"]
    if key in _cache and time.time() - _cache[key][0] < 600: return _cache[key][1]
    params = {"latitude":district["latitude"],"longitude":district["longitude"],"daily":"temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max","current":"temperature_2m,relative_humidity_2m,precipitation","timezone":"Asia/Kolkata","forecast_days":7}
    async with httpx.AsyncClient(timeout=8) as client:
        res = await client.get("https://api.open-meteo.com/v1/forecast", params=params); res.raise_for_status(); raw = res.json()
    d = raw["daily"]
    daily = [{"date":d["time"][i],"max":d["temperature_2m_max"][i],"min":d["temperature_2m_min"][i],"rain":d["precipitation_sum"][i] or 0,"rain_probability":d["precipitation_probability_max"][i] or 0,"wind":d["wind_speed_10m_max"][i] or 0} for i in range(len(d["time"]))]
    next48 = daily[:2]
    flags = []
    if any(x["rain"] >= 25 or x["rain_probability"] >= 80 for x in daily): flags.append("heavy_rain")
    if any(x["rain_probability"] >= 60 for x in next48): flags.append("rain_soon")
    if sum(x["rain"] for x in daily) < 5: flags.append("dry_spell")
    if any(x["max"] is not None and x["max"] >= 40 for x in daily): flags.append("heat")
    if any(x["wind"] >= 25 for x in daily): flags.append("wind_high")
    result = {"current":raw.get("current",{}),"daily":daily,"flags":flags,"source":"Open-Meteo"}
    _cache[key] = (time.time(), result); return result
