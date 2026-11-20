import os, time
from collections import defaultdict, deque
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from services.weather import DISTRICTS, district_for, get_weather, debug_weather
from services.mandi import get_mandi
from services.ai import generate
from services.crop_doctor import diagnose as diagnose_crop, debug_gemini

load_dotenv(Path(__file__).parent / ".env")
app=FastAPI(title="Kisan Mitra API",version="1.0.0")
origin=os.getenv("ALLOWED_ORIGIN","http://localhost:5173")
app.add_middleware(CORSMiddleware,allow_origins=[origin],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["Content-Type"])
hits=defaultdict(deque)
diagnose_hits=defaultdict(deque)
@app.middleware("http")
async def rate_limit(request, call_next):
    q=hits[request.client.host]; now=time.time()
    while q and now-q[0]>60: q.popleft()
    if len(q)>=30: return __import__("fastapi").responses.JSONResponse({"detail":"Too many requests"},status_code=429)
    q.append(now); return await call_next(request)

class AdviceRequest(BaseModel):
    district:str; crop:str; language:str=Field(pattern="^(mr|hi|en)$")
class AskRequest(AdviceRequest): question:str=Field(min_length=1,max_length=1000)

MAX_DIAGNOSIS_IMAGE_BYTES=4*1024*1024
IMAGE_TYPES={".jpg":("image/jpeg",b"\xff\xd8\xff"),".jpeg":("image/jpeg",b"\xff\xd8\xff"),".png":("image/png",b"\x89PNG\r\n\x1a\n"),".webp":("image/webp",b"RIFF")}

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

@app.post("/api/diagnose")
async def diagnose_endpoint(
    request:Request,
    image:UploadFile=File(...),
    crop:str=Form(...),
    district:str=Form(...),
    language:str=Form(...),
):
    now=time.time(); host=request.client.host if request and request.client else "unknown"; bucket=diagnose_hits[host]
    while bucket and now-bucket[0]>60: bucket.popleft()
    if len(bucket)>=10: raise HTTPException(429,"Too many crop diagnosis requests; try again in a minute")
    if language not in {"mr","hi","en"}: raise HTTPException(422,"language must be mr, hi or en")
    if not crop.strip(): raise HTTPException(422,"crop is required")
    try: selected_district=district_for(district)
    except ValueError as exc: raise HTTPException(400,"Unknown district") from exc
    suffix=Path(image.filename or "").suffix.lower(); accepted=IMAGE_TYPES.get(suffix)
    if not accepted or image.content_type!=accepted[0]:
        raise HTTPException(415,"Upload a JPG, PNG or WEBP image")
    data=await image.read(MAX_DIAGNOSIS_IMAGE_BYTES+1)
    await image.close()
    if len(data)>MAX_DIAGNOSIS_IMAGE_BYTES: raise HTTPException(413,"Image must be 4 MB or smaller")
    expected_magic=accepted[1]
    valid_signature=data.startswith(expected_magic)
    if suffix==".webp": valid_signature=valid_signature and data[8:12]==b"WEBP"
    if not valid_signature: raise HTTPException(415,"The image contents do not match its file type")
    bucket.append(now)
    return await diagnose_crop(data,accepted[0],crop.strip(),selected_district,language)

@app.get("/api/debug/gemini")
async def gemini_debug():
    return await debug_gemini()
