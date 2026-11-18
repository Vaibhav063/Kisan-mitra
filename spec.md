# Kisan Mitra (किसान मित्र) – Project Spec

> Instruction to the AI builder (Codex, Antigravity or any coding agent): Read this whole file first. Build the whole project as specified, following the "Build Order" at the bottom, and do not stop to ask for confirmation between steps unless you are blocked. The owner is a beginner on Windows (PowerShell, VS Code), so give simple copy-paste commands, explain what to expect, and never skip setup steps. Do not add features outside this spec. If a UI design reference exists in the design/ folder, build the working app first and only then match the visual style using screenshot images, one at a time.

## 1. Overview

**Kisan Mitra** is a free, mobile-first web app. A small farmer in India picks a language, district and crop, then gets (a) a short AI-written "what to do today" recommendation, (b) a 7-day weather view with risk alerts, (c) a mandi price comparison for nearby markets, and (d) can ask free-form questions by voice or text. All AI answers are in simple Marathi, Hindi or English and can be read aloud.

**Target user:** Small and marginal farmers in rain-fed regions (Marathwada, Vidarbha), many with low literacy and limited English.

**Problem:** Farmers lack timely, personalised, local-language advice on when to sow, spray, irrigate, harvest and sell. Weather apps are in English, mandi data sits in hard-to-read government portals, and wrong timing causes crop and income loss.

**Hackathon:** IDEA//FORGE Online Hackathon, Track 2 (Multilingual Agritech & Resource Advisory Assistant). AI must do real work: combining weather + prices + question into a grounded, local-language decision.

## 2. Hard constraints

- **Free tools only.** No paid APIs or services (no Twilio, no paid TTS, no paid databases).
- **Frontend deployed on Vercel. Backend deployed on Render (free web service).**
- No login, no database. Keep everything stateless; store the farmer's choices (language, district, crop) in browser `localStorage`.
- API keys only in backend environment variables. Never in frontend code or GitHub.
- Must work on a phone browser and in an incognito window.
- Credits page/footer must list: Google Gemini, Open-Meteo, data.gov.in (Agmarknet), Vercel, Render, Web Speech API.

## 3. Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite + Tailwind CSS (mobile-first, single page with tabs) |
| Backend | Python 3.11 + FastAPI + Uvicorn |
| AI | Google Gemini via `google-genai` Python SDK, model name from env var `GEMINI_MODEL` (default: the current free Flash model shown in Google AI Studio) |
| Weather | Open-Meteo forecast API (free, no key) |
| Mandi prices | data.gov.in Agmarknet "Current daily price of various commodities from various markets (Mandi)" API, free key |
| Voice input | Browser Web Speech API (`SpeechRecognition`), lang `mr-IN`, `hi-IN`, `en-IN` |
| Voice output | Browser `speechSynthesis` (fallback to Hindi voice if Marathi voice is unavailable; always show text too) |
| Uptime | UptimeRobot (free) pinging `/health` every 5 minutes |

## 3.1 Folder structure

```
kisan-mitra/
  backend/
    main.py            # FastAPI app, routes, CORS
    services/
      weather.py       # Open-Meteo calls
      mandi.py         # data.gov.in calls + fallback
      ai.py            # Gemini prompt + call
    data/
      districts.json   # district -> lat/lon
      mandi_fallback.json
    requirements.txt
    .env.example
  frontend/
    src/
      App.jsx
      components/ (Onboarding, TodayCard, AskBox, MandiTable, WeatherStrip, AlertBanner, LanguageSwitch)
      i18n.js          # UI strings in mr, hi, en
      api.js           # calls backend using VITE_API_URL
    .env.example
  README.md
  spec.md
```

## 4. Environment variables

Backend (`backend/.env`, and set the same on Render):
```
GEMINI_API_KEY=
GEMINI_MODEL=
DATA_GOV_API_KEY=
ALLOWED_ORIGIN=https://<your-vercel-app>.vercel.app
```
Frontend (`frontend/.env`, and set on Vercel):
```
VITE_API_URL=https://<your-render-service>.onrender.com
```
For local testing: `ALLOWED_ORIGIN=http://localhost:5173`, `VITE_API_URL=http://localhost:8000`.

## 5. Data

### 5.1 Districts (starter list in `districts.json`)
Include name (English, Marathi, Hindi), state, latitude, longitude. Start with these Maharashtra districts (verify coordinates):
Chhatrapati Sambhajinagar (19.8762, 75.3433), Jalna (19.8347, 75.8816), Beed (18.9890, 75.7601), Latur (18.4088, 76.5604), Nanded (19.1383, 77.3210), Parbhani (19.2704, 76.7747), Solapur (17.6599, 75.9064), Pune (18.5204, 73.8567), Nashik (19.9975, 73.7898), Nagpur (21.1458, 79.0882), Akola (20.7002, 77.0082), Yavatmal (20.3899, 78.1307).

### 5.2 Crops
Soybean, Cotton, Tur (pigeon pea), Wheat, Onion. Map each to its Agmarknet commodity name (verify exact spelling against the API; e.g. "Soyabean", "Cotton", "Arhar (Tur/Red Gram)(Whole)", "Wheat", "Onion"). Each crop has a Marathi, Hindi and English display name.

### 5.3 Weather (Open-Meteo)
`GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max&current=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia%2FKolkata&forecast_days=7`

Backend derives risk flags from daily data:
- `heavy_rain`: precipitation_sum >= 25 mm or probability >= 80%
- `rain_soon`: any rain probability >= 60% in next 48 hours (do not spray)
- `dry_spell`: total rain < 5 mm over 7 days
- `heat`: temperature max >= 40 C
- `wind_high`: wind max >= 25 km/h (do not spray)

### 5.4 Mandi prices (data.gov.in)
Resource ID: `9ef84268-d588-465a-a308-a864a43d0070`
`GET https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key={KEY}&format=json&limit=200&filters[state.keyword]=Maharashtra&filters[commodity]={commodity}`
Expected fields: state, district, market, commodity, variety, arrival_date, min_price, max_price, modal_price (Rs per quintal). Verify field and filter names against the live response and adapt.
Logic: prefer markets in the selected district, then neighbouring districts in the state; return up to 5 markets sorted by modal_price descending; mark the highest as `best`. If the API fails, is empty or times out (>8 s), load `data/mandi_fallback.json` and set `source: "sample"` so the UI shows "Sample data" badge.

## 6. Backend API

All responses JSON. Enable CORS only for `ALLOWED_ORIGIN`.

- `GET /health` -> `{"status":"ok"}`
- `GET /api/weather?district=&` -> `{ current, daily[7], flags[] }`
- `GET /api/mandi?district=&crop=` -> `{ markets[{market,district,min,max,modal,date}], best_market, source }`
- `POST /api/advice` body `{district, crop, language}` -> fetches weather + mandi, calls Gemini, returns:
```
{ "headline": "string (max 12 words)",
  "actions": [ {"type":"spray|irrigate|sow|harvest|sell|wait","text":"string","urgency":"low|medium|high"} ],
  "explanation": "string (2-4 short sentences)",
  "alerts": ["string"],
  "weather_flags": [], "best_market": {}, "source_notes": "string" }
```
- `POST /api/ask` body `{district, crop, language, question}` -> fetches same context, returns `{ "answer": "string", "alerts": [] }`

Add simple in-memory caching (10 minutes for weather, 30 minutes for mandi) keyed by district/crop. Add basic rate limiting (e.g. 30 requests per minute per IP) to protect the free Gemini quota. On Gemini errors, return a friendly message and a rule-based fallback advice built from the weather flags (so the app never shows a blank screen).

## 7. Gemini prompt design (`services/ai.py`)

Use a system instruction like:

> You are Kisan Mitra, a friendly farm advisor for small farmers in India. Reply ONLY in {language} (Marathi, Hindi or English) using very simple, short, everyday words a farmer would use. Use ONLY the weather and mandi data provided below. Never invent prices, dates or weather. Never give pesticide or fertiliser dosages; instead say to ask the local Krishi Vigyan Kendra or agriculture officer for dosage. If data is missing, say so honestly. Give practical advice for today and the next 3 days. Always mention the main reason (for example "rain expected on Thursday"). Keep the answer under 120 words. Be respectful and encouraging.

User content: JSON containing district, crop, today's date, 7-day weather, risk flags, mandi list, and (for /api/ask) the farmer's question. Request structured JSON output for `/api/advice` and strip code fences before parsing. Keep temperature low (about 0.3).

## 8. Frontend screens (mobile-first, bottom tab bar)

1. **Onboarding:** choose language (large buttons: मराठी / हिंदी / English), district (dropdown), crop (big icon cards). Save to localStorage. "Start" button.
2. **Home / Today:** greeting, alert banner (if any flags), "Today's advice" card with headline, action chips (spray, irrigate, wait, sell...) with urgency colours, short explanation, a "Listen" speaker button, and a small weather summary.
3. **Ask:** large mic button (tap to speak), text input fallback, example question chips ("Should I spray today?", "Where should I sell?", "Will it rain this week?"), chat-style answer with Listen button.
4. **Mandi:** crop price table for up to 5 markets (min / max / modal in Rs per quintal), best market highlighted, "Sample data" badge when fallback is used, date of prices.
5. **Weather:** 7-day strip with icons, rain %, temperature, wind, and plain-language risk notes.
6. **Settings/About:** change language, district and crop; credits; short "How it works" and responsible-AI note.

Responsive layout: this is a website that must look good on BOTH phones and laptops. Design mobile-first, then adapt. On screens under 768 px use the bottom tab bar and single-column cards. On 768 px and wider use a left sidebar (or top navigation) instead of the bottom bar, center the content with a max width of about 1100 px, and arrange cards in a 2-column grid (for example: Today's advice on the left, weather summary and mandi highlight on the right). Keep the same colors, fonts and components on every screen size.

UI rules: large touch targets (min 48 px), big readable fonts (Marathi/Hindi need a Devanagari-friendly font such as Noto Sans Devanagari via Google Fonts), high contrast, green and earthy colours, icons plus text, loading skeletons, and a "Waking up the server, please wait" message if the first request takes longer than 5 seconds (Render free tier cold start). All UI text comes from `i18n.js` in mr / hi / en.

## 9. Voice rules

- Speech input uses `SpeechRecognition` / `webkitSpeechRecognition` with the language set from the chosen language. If unsupported, hide the mic and show text input only.
- Speech output uses `speechSynthesis`. Choose a voice matching the language; if no Marathi voice exists, use a Hindi voice; if none, hide the Listen button gracefully.

## 10. Error handling and safety

- Never show raw errors. Show friendly local-language messages and a retry button.
- Show a small disclaimer on advice cards: "AI advice. For pesticide dosage and serious crop problems, contact your local agriculture officer."
- Never store personal data. No analytics.

## 11. Deployment

- **Backend on Render:** Web Service from the GitHub repo, root directory `backend`, build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`, free plan, add env vars.
- **Frontend on Vercel:** import the GitHub repo, root directory `frontend`, framework Vite, add `VITE_API_URL`.
- Add UptimeRobot monitor for `https://<render-url>/health` every 5 minutes.
- Write a beginner-friendly `README.md` with setup, run, and deploy steps, and the credits list.

## 12. Acceptance criteria (must all pass)

1. A new user can pick Marathi, Beed, Soybean and see a Marathi advice card within 10 seconds (after cold start).
2. The Ask tab answers a spoken or typed question in the chosen language using the supplied weather and prices.
3. The mandi tab shows real prices, or clearly labelled sample data when the API fails.
4. The app works on a phone and in an incognito window; both public links open without login.
5. No API key is visible in the frontend code, network calls to third parties from the browser, or GitHub.
6. The app never crashes when Gemini, Open-Meteo or data.gov.in fail.

## 13. Out of scope (do NOT build)

User accounts, databases, payments, WhatsApp/SMS, satellite imagery, push notifications, crop-disease photo diagnosis (optional stretch only after everything above works).

## 13.1 Windows notes

- The owner uses Windows with PowerShell and VS Code. Give PowerShell-compatible commands (for example `py -m venv .venv`, `.venv\Scripts\Activate.ps1`, `pip install -r requirements.txt`, `uvicorn main:app --reload`; for frontend `npm install`, `npm run dev`).
- If PowerShell blocks script activation, tell the owner to run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Avoid commands that only work on Linux/macOS (such as `export`, `source`, `rm -rf`).
- Project folder path may contain spaces; quote paths in commands.

## 14. Build order

1. Create the repo structure, `requirements.txt`, `.env.example`, and a `/health` route; give me the commands to run it locally.
2. Weather service and `/api/weather` with risk flags; test with a sample district.
3. Mandi service and `/api/mandi` with fallback data; test.
4. Gemini service, `/api/advice` and `/api/ask`, with fallback advice; test in Marathi, Hindi and English.
5. Frontend: i18n, onboarding, Home, Ask, Mandi, Weather, Settings; connect to the backend.
6. Voice input and output.
7. Polish UI to match the Stitch design reference (if provided), loading and error states.
8. Deployment steps for Render and Vercel, plus UptimeRobot.
9. Final testing checklist from section 12.
