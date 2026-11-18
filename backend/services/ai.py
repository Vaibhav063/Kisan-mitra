import json, os
import re
from google import genai

LANG = {"mr":"Marathi","hi":"Hindi","en":"English"}

def fallback_advice(weather, mandi, language):
    messages = {
      "mr": {"headline":"आज शेताची काळजीपूर्वक पाहणी करा","wait":"पाऊस किंवा जोरदार वारा अपेक्षित आहे. फवारणी थांबवा.","dry":"पाऊस कमी आहे. जमिनीत ओलावा तपासून गरजेनुसार पाणी द्या.","ok":"पीक आणि जमिनीतील ओलावा पाहून आजचे काम ठरवा.","reason":"हा सल्ला उपलब्ध हवामान आणि बाजार माहितीनुसार आहे."},
      "hi": {"headline":"आज खेत की सावधानी से जाँच करें","wait":"बारिश या तेज हवा संभव है। छिड़काव रोकें।","dry":"बारिश कम है। मिट्टी की नमी देखकर जरूरत पर पानी दें।","ok":"फसल और मिट्टी की नमी देखकर आज का काम तय करें।","reason":"यह सलाह उपलब्ध मौसम और मंडी जानकारी पर आधारित है।"},
      "en": {"headline":"Check your crop carefully today","wait":"Rain or strong wind is expected. Avoid spraying.","dry":"Rain is low. Check soil moisture and irrigate if needed.","ok":"Check the crop and soil moisture before deciding today's work.","reason":"This uses the available weather and market information."}}
    t=messages.get(language,messages["en"]); flags=weather.get("flags",[])
    action = t["wait"] if "rain_soon" in flags or "wind_high" in flags or "heavy_rain" in flags else t["dry"] if "dry_spell" in flags else t["ok"]
    return {"headline":t["headline"],"actions":[{"type":"wait" if action==t["wait"] else "irrigate","text":action,"urgency":"medium" if flags else "low"}],"explanation":t["reason"],"alerts":[action] if flags else [],"weather_flags":flags,"best_market":mandi.get("best_market"),"source_notes":"Rule-based fallback; verify local conditions."}

def _day(value, language):
    try:
        from datetime import date
        names={"mr":["सोमवार","मंगळवार","बुधवार","गुरुवार","शुक्रवार","शनिवार","रविवार"],"hi":["सोमवार","मंगलवार","बुधवार","गुरुवार","शुक्रवार","शनिवार","रविवार"],"en":["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}
        return names.get(language,names["en"])[date.fromisoformat(str(value)).weekday()]
    except Exception: return str(value or "")

def _fallback_ask(question, weather, mandi, language):
    lang=language if language in ("mr","hi","en") else "en"
    q=(question or "").lower()
    daily=weather.get("daily") or []
    w={"en":{"why":"Why","what":"What to do","basic":"Basic advice"},"mr":{"why":"का?","what":"काय करावे?","basic":"मूलभूत सल्ला"},"hi":{"why":"क्यों?","what":"क्या करें?","basic":"मूल सलाह"}}[lang]
    def txt(en,mr,hi): return {"en":en,"mr":mr,"hi":hi}[lang]
    reasons=[]; steps=[]; caution=None
    if any(k in q for k in ("sell","market","विकू","विक्री","विकावे","बेच","कहाँ")):
        markets=mandi.get("markets") or []; best=max(markets,key=lambda m:m.get("modal",0)) if markets else mandi.get("best_market")
        if best:
            answer=txt(f"Sell at {best.get('market')}; it has the best available modal price.",f"{best.get('market')} येथे विक्री करा; उपलब्ध बाजारांत तेथे सर्वाधिक भाव आहे.",f"{best.get('market')} में बेचें; उपलब्ध मंडियों में यहाँ सबसे अच्छा भाव है।")
            for m in markets[:3]: reasons.append(f"{m.get('market')}: ₹{m.get('modal')} per quintal")
            steps=[txt("Compare today's modal prices before leaving.","निघण्यापूर्वी आजचे बाजारभाव तपासा.","निकलने से पहले आज के मंडी भाव जाँचें."),txt(f"Ask {best.get('market')} for today's arrival and buying status.",f"{best.get('market')} मध्ये आजची आवक व खरेदीची स्थिती विचारा.",f"{best.get('market')} में आज की आवक और खरीद की स्थिति पूछें.")]
        else: answer=txt("I cannot recommend a market because mandi prices are missing.","मंडीचे भाव उपलब्ध नसल्याने बाजार सुचवता येत नाही.","मंडी भाव उपलब्ध नहीं हैं, इसलिए बाजार नहीं बता सकता।"); reasons=[txt("Mandi prices are missing.","मंडीचे भाव उपलब्ध नाहीत.","मंडी भाव उपलब्ध नहीं हैं।")]; steps=[txt("Check today's local mandi prices before selling.","विक्रीपूर्वी आजचे स्थानिक बाजारभाव तपासा.","बेचने से पहले आज के स्थानीय मंडी भाव जाँचें.")]
    elif any(k in q for k in ("rain","पाऊस","बारिश","वर्षा")):
        if daily:
            wet=[d for d in daily[:7] if (d.get("rain_probability") or 0)>=40 or (d.get("rain") or 0)>=2]
            if wet:
                d=wet[0]; day=_day(d.get("date"),lang); answer=txt(f"Rain is possible this week, especially {day}.",f"या आठवड्यात पावसाची शक्यता आहे, विशेषतः {day}.",f"इस हफ्ते बारिश संभव है, खासकर {day} को।")
            else: answer=txt("No notable rain signal appears in the available 7-day forecast.","उपलब्ध ७ दिवसांच्या अंदाजात लक्षणीय पावसाचा संकेत नाही.","उपलब्ध 7-दिन के पूर्वानुमान में बारिश का खास संकेत नहीं है।")
            for d in daily[:4]: reasons.append(f"{_day(d.get('date'),lang)}: {d.get('rain_probability','—')}% / {d.get('rain','—')} mm")
            steps=[txt("Check the forecast again each morning.","दररोज सकाळी अंदाज पुन्हा तपासा.","हर सुबह पूर्वानुमान फिर जाँचें."),txt("Keep harvested produce covered if rain is forecast.","पावसाचा अंदाज असल्यास काढलेले पीक झाकून ठेवा.","बारिश का अनुमान हो तो कटी फसल ढककर रखें.")]
        else: answer=txt("I cannot tell whether it will rain because the 7-day forecast is missing.","७ दिवसांचा अंदाज उपलब्ध नसल्याने पाऊस सांगता येत नाही.","7-दिन का पूर्वानुमान उपलब्ध नहीं है, इसलिए बारिश नहीं बता सकता।"); reasons=[txt("The 7-day rain forecast is missing.","७ दिवसांचा पावसाचा अंदाज उपलब्ध नाही.","7-दिन का बारिश पूर्वानुमान उपलब्ध नहीं है।")]; steps=[txt("Check the local forecast before field work.","शेतातील कामापूर्वी स्थानिक अंदाज तपासा.","खेत के काम से पहले स्थानीय पूर्वानुमान जाँचें.")]
    elif any(k in q for k in ("spray","फवार","छिड़क","छिडक")):
        next48=daily[:2]; missing=not next48 or any(d.get("rain_probability") is None or d.get("wind") is None for d in next48); risk=any((d.get("rain_probability") or 0)>=60 or (d.get("wind") or 0)>=25 for d in next48)
        risk_indices=[i for i,d in enumerate(next48) if (d.get("rain_probability") or 0)>=60 or (d.get("wind") or 0)>=25]
        wait_index=min(risk_indices[-1]+1,len(daily)-1) if risk_indices and daily else 0
        waitday=daily[wait_index] if daily else {}
        if missing:
            answer=txt("I cannot confirm spraying is safe because the next 48-hour rain and wind forecast is missing.","पुढील ४८ तासांचा पाऊस व वाऱ्याचा अंदाज उपलब्ध नसल्याने फवारणी सुरक्षित आहे का हे सांगता येत नाही.","अगले 48 घंटे की बारिश और हवा का पूर्वानुमान नहीं है, इसलिए छिड़काव सुरक्षित है या नहीं बता नहीं सकता।")
        elif risk:
            day=_day(waitday.get("date"),lang) if waitday else txt("after the forecast is available","अंदाज उपलब्ध झाल्यावर","पूर्वानुमान मिलने पर")
            answer=txt(f"Do not spray today; wait until {day} and recheck the weather.",f"आज फवारणी करू नका; {day} पर्यंत थांबा आणि हवामान पुन्हा तपासा.",f"आज छिड़काव न करें; {day} तक रुकें और मौसम फिर जाँचें।")
        else: answer=txt("Spraying looks suitable today; do it early, before 10 AM.","आज फवारणी योग्य दिसते; सकाळी १० वाजण्यापूर्वी करा.","आज छिड़काव ठीक लग रहा है; सुबह 10 बजे से पहले करें।")
        for d in next48: reasons.append(f"{_day(d.get('date'),lang)}: rain {d.get('rain_probability','—')}% / {d.get('rain','—')} mm; wind {d.get('wind','—')} km/h")
        if not reasons: reasons=[txt("The next 48-hour rain and wind forecast is missing.","पुढील ४८ तासांचा पाऊस व वाऱ्याचा अंदाज उपलब्ध नाही.","अगले 48 घंटे की बारिश और हवा का पूर्वानुमान उपलब्ध नहीं है।")]
        steps=[txt("Spray only when leaves are dry and wind is light.","पाने कोरडी आणि वारा मंद असताना फवारणी करा.","पत्ते सूखे और हवा हल्की हो तभी छिड़काव करें."),txt("Avoid spraying before forecast rain or in strong wind.","पावसापूर्वी किंवा जोरदार वाऱ्यात फवारणी टाळा.","बारिश से पहले या तेज हवा में छिड़काव न करें.")]
    else:
        if daily:
            rain=daily[0].get("rain_probability","—"); mm=daily[0].get("rain","—"); answer=txt("Irrigate only if the root zone is dry; rain is not a reason to irrigate today.","मुळांजवळची जमीन कोरडी असेल तरच पाणी द्या; आजचा पाऊस पाहून ठरवा.","जड़ के पास मिट्टी सूखी हो तभी सिंचाई करें; आज की बारिश देखकर तय करें।")
            reasons=[txt(f"Today: {rain}% rain chance, {mm} mm forecast.",f"आज: पावसाची शक्यता {rain}%, अंदाजे {mm} मिमी.",f"आज: बारिश की संभावना {rain}%, अनुमान {mm} मिमी."),txt(f"Wind is {daily[0].get('wind','—')} km/h and temperature is {daily[0].get('max','—')}°C.",f"वारा {daily[0].get('wind','—')} किमी/तास; कमाल तापमान {daily[0].get('max','—')}°C.",f"हवा {daily[0].get('wind','—')} किमी/घंटा; अधिकतम तापमान {daily[0].get('max','—')}°C.")]
        else: answer=txt("I cannot advise irrigation because today's forecast is missing.","आजचा अंदाज उपलब्ध नसल्याने पाणी देण्याचा सल्ला देता येत नाही.","आज का पूर्वानुमान उपलब्ध नहीं है, इसलिए सिंचाई की सलाह नहीं दे सकता।"); reasons=[txt("Today's rain forecast is missing.","आजचा पावसाचा अंदाज उपलब्ध नाही.","आज का बारिश पूर्वानुमान उपलब्ध नहीं है।")]
        steps=[txt("Check soil moisture near the roots this morning.","आज सकाळी मुळांजवळील ओलावा तपासा.","आज सुबह जड़ों के पास मिट्टी की नमी जाँचें."),txt("If dry, irrigate in the early morning; skip if rain wets the soil.","जमीन कोरडी असल्यास सकाळी पाणी द्या; पावसाने ओली झाल्यास टाळा.","मिट्टी सूखी हो तो सुबह सिंचाई करें; बारिश से गीली हो तो छोड़ दें.")]
    return {"answer":answer,"reasons":reasons[:4],"steps":steps[:3],"caution":caution,"basic_advice":True}

ASK_SYSTEM="""You are Kisan Mitra, a practical farm advisor. Reply only in the selected language (simple everyday Marathi, Hindi, or English). Return ONLY valid JSON with keys answer (one direct sentence answering the exact question), reasons (2-4 short strings), steps (2-3 simple timed actions), and optional caution (short string). Keep the complete response under 120 words. Answer the exact question first. Use supplied data only; include actual rain probability and mm for today and next three days, wind in km/h, temperatures, and for selling, actual market names and modal prices per quintal plus the best market. Adapt reasons and actions to spraying, irrigation, sowing, harvest, selling, or rain. Name missing data exactly; do not mention data sources unless needed to explain missing data. Never use generic disclaimers, invent numbers/dates/markets, or give chemical/pesticide dosages. For dosage requests, direct the farmer to the local Krishi Vigyan Kendra or agriculture officer."""

def _clean_json(text):
    text=(text or "").strip()
    text=re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    return json.loads(text)

def _normalize_ask(data):
    if not isinstance(data,dict) or not isinstance(data.get("answer"),str): raise ValueError("Missing direct answer")
    result={"answer":data["answer"].strip(),"reasons":data.get("reasons",[]),"steps":data.get("steps",[])}
    if not isinstance(result["reasons"],list) or not isinstance(result["steps"],list): raise ValueError("Invalid lists")
    result["reasons"]=[str(x).strip() for x in result["reasons"] if str(x).strip()][:4]
    result["steps"]=[str(x).strip() for x in result["steps"] if str(x).strip()][:3]
    if not 2<=len(result["reasons"])<=4 or not 2<=len(result["steps"])<=3: raise ValueError("Invalid list lengths")
    words=(result["answer"]+" "+" ".join(result["reasons"]+result["steps"]+([str(data["caution"])] if data.get("caution") else []))).split()
    if len(words)>120: raise ValueError("Over 120 words")
    if data.get("caution"): result["caution"]=str(data["caution"]).strip()
    return result

async def generate(kind, district, crop, language, weather, mandi, question=None):
    key=os.getenv("GEMINI_API_KEY","")
    fallback=fallback_advice(weather,mandi,language)
    if kind!="advice" and kind=="ask":
        basic=_fallback_ask(question,weather,mandi,language)
        if not key: return basic
        context={"question":question,"district":district["name"].get("en"),"crop":crop,"language":LANG.get(language,"English"),"weather":weather,"mandi":mandi}
        try:
            client=genai.Client(api_key=key)
            response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.0-flash"),contents=ASK_SYSTEM+"\nContext JSON: "+json.dumps(context,ensure_ascii=False),config={"temperature":0.2,"response_mime_type":"application/json"})
            return _normalize_ask(_clean_json(response.text))
        except Exception: return basic
    if not key: return fallback
    prompt={"district":district["name"]["en"],"crop":crop,"today":"today","weather":weather,"markets":mandi,"question":question}
    system=f"You are Kisan Mitra, friendly farm advisor for small farmers in India. Reply only in {LANG.get(language,'English')} using simple short everyday words. Use only supplied weather and mandi data. Never invent prices, dates, or weather. Never give pesticide/fertiliser dosages; direct farmers to local agriculture officer. If missing, say so honestly. Practical advice for today and next 3 days, explain reason, under 120 words."
    try:
        client=genai.Client(api_key=key)
        response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.0-flash"),contents=system+"\nContext JSON: "+json.dumps(prompt,ensure_ascii=False),config={"temperature":0.3,"response_mime_type":"application/json"})
        result=json.loads(_clean_json(response.text)); result.setdefault("weather_flags",weather.get("flags",[])); result.setdefault("best_market",mandi.get("best_market")); result.setdefault("source_notes","Weather: Open-Meteo. Mandi: "+mandi["source"]); result.setdefault("alerts",[]); return result
    except Exception: return fallback
