import os, time
from collections import defaultdict, deque
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from services.weather import DISTRICTS, district_for, get_weather, debug_weather
from services.mandi import get_mandi
from services.ai import generate

load_dotenv(Path(__file__).parent / ".env")
app=FastAPI(title="Kisan Mitra API",version="1.0.0")
origin=os.getenv("ALLOWED_ORIGIN","http://localhost:5173")
app.add_middleware(CORSMiddleware,allow_origins=[origin],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["Content-Type"])
hits=defaultdict(deque)
@app.middleware("http")
async def rate_limit(request, call_next):
    q=hits[request.client.host]; now=time.time()
    while q and now-q[0]>60: q.popleft()
    if len(q)>=30: return __import__("fastapi").responses.JSONResponse({"detail":"Too many requests"},status_code=429)
    q.append(now); return await call_next(request)

class AdviceRequest(BaseModel):
    district:str; crop:str; language:str=Field(pattern="^(mr|hi|en)$")
class AskRequest(AdviceRequest): question:str=Field(min_length=1,max_length=1000)

@app.get("/health")
async def health(): return {"status":"ok"}
@app.get("/api/districts")
async def districts(): return DISTRICTS
@app.get("/api/weather")
async def weather(district:str):
    try:return await get_weather(district_for(district))
    except ValueError as e: raise HTTPException(400,"Unknown district") from e
    except Exception: return {"current":{},"daily":[],"flags":[],"source":"unavailable","message":"Weather data is temporarily unavailable"}
@app.get("/api/debug/weather")
async def weather_debug(district:str):
    try:return await debug_weather(district_for(district))
    except ValueError as e: raise HTTPException(400,"Unknown district") from e
@app.get("/api/mandi")
async def mandi(district:str,crop:str):
    try:return await get_mandi(district_for(district),crop)
    except ValueError as e: raise HTTPException(400,"Unknown district or crop") from e
@app.post("/api/advice")
async def advice(body:AdviceRequest):
    try:
        d=district_for(body.district); w=await get_weather(d); m=await get_mandi(d,body.crop)
    except ValueError: raise HTTPException(400,"Unknown district or crop")
    except Exception: w={"current":{},"daily":[],"flags":[],"source":"unavailable"}; m=await get_mandi(d,body.crop)
    return await generate("advice",d,body.crop,body.language,w,m)
@app.post("/api/ask")
async def ask(body:AskRequest):
    try:
        d=district_for(body.district); w=await get_weather(d); m=await get_mandi(d,body.crop)
    except ValueError: raise HTTPException(400,"Unknown district or crop")
    except Exception: w={"current":{},"daily":[],"flags":[],"source":"unavailable"}; m=await get_mandi(d,body.crop)
    return await generate("ask",d,body.crop,body.language,w,m,body.question)
