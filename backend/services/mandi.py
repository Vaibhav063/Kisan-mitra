import json, os, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
FALLBACK = json.loads((ROOT / "data/mandi_fallback.json").read_text(encoding="utf-8"))
CROPS = {"soybean":("Soybean","Soyabean"),"cotton":("Cotton","Cotton"),"tur":("Tur (pigeon pea)","Arhar (Tur/Red Gram)(Whole)"),"wheat":("Wheat","Wheat"),"onion":("Onion","Onion")}
_cache = {}
CACHE_TTL = 30 * 60

async def get_mandi(district, crop):
    normalized = crop.lower()
    if normalized not in CROPS: raise ValueError("Unknown crop")
    display, commodity = CROPS[normalized]; key = (district["id"], normalized)
    if key in _cache and time.time()-_cache[key][0] < CACHE_TTL: return _cache[key][1]
    result = None
    api_key = os.getenv("DATA_GOV_API_KEY", "")
    if api_key:
        try:
            params = {"api-key":api_key,"format":"json","limit":200,"filters[state.keyword]":"Maharashtra","filters[commodity]":commodity}
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get("https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070", params=params); response.raise_for_status(); records = response.json().get("records", [])
            markets = [{"market":r.get("market",""),"district":r.get("district",""),"min":int(float(r.get("min_price") or 0)),"max":int(float(r.get("max_price") or 0)),"modal":int(float(r.get("modal_price") or 0)),"date":r.get("arrival_date","")} for r in records if r.get("modal_price")]
            markets.sort(key=lambda m:(m["district"].lower()==district["name"]["en"].lower(),m["modal"]), reverse=True)
            if markets: result = {"markets":markets[:5],"best_market":markets[0],"source":"data.gov.in"}
        except Exception: pass
    if not result:
        markets = FALLBACK.get(display, FALLBACK["Soybean"])
        sorted_markets=sorted(markets,key=lambda m:(m["district"].lower()==district["name"]["en"].lower(),m["modal"]),reverse=True)[:5]
        result = {"markets":sorted_markets,"best_market":sorted_markets[0],"source":"sample"}
    _cache[key]=(time.time(),result); return result
