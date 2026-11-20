# Kisan Mitra ðŸŒ±

Kisan Mitra is a free, multilingual farm companion for small farmers. It brings local crop advice, weather forecasts, mandi prices, voice or text questions, and Crop Doctor photo guidance into one mobile-friendly app. The interface is available in Marathi, Hindi, and English.

## The problem and who it serves

Small and marginal farmers, especially in rain-fed regions such as Marathwada and Vidarbha, often need to check weather, market prices, and crop guidance across different services and languages. Delayed or hard-to-understand information can make decisions about spraying, irrigation, harvesting, and selling more difficult. Kisan Mitra presents these information sources together in familiar local languages.

## Features

- Daily crop advice informed by weather and mandi information, with a rule-based fallback.
- Seven-day forecast and plain-language weather risk flags.
- Nearby mandi price comparison, with clearly labelled sample prices when live data is unavailable.
- Ask a farm question by typing or supported browser speech recognition, then listen to the answer.
- Crop Doctor: upload or take a crop-leaf photo for a possible AI diagnosis and practical next steps.
- Marathi, Hindi, and English interface; the selected district, crop, and language are stored in this browser only.
- Responsive landing page and app, with a bottom tab bar on phones and a sidebar on wider screens.

## Architecture

```text
Browser (React + Vite + Tailwind)
  â””â”€â”€ FastAPI backend
       â”œâ”€â”€ Gemini: advice, Ask, and Crop Doctor
       â”œâ”€â”€ Open-Meteo, then MET Norway: weather
       â””â”€â”€ data.gov.in Agmarknet: mandi prices, with bundled sample fallback
```

The frontend calls the backend using `VITE_API_URL`. API keys stay on the backend. The app has no login, database, analytics, or server-side user profile. Successful backend responses are cached in memory while the browser session is open; the backend also uses small in-memory caches.

## Tech stack and free tools

- Frontend: React, Vite, Tailwind CSS, and Lucide icons.
- Backend: Python 3.11+, FastAPI, and Uvicorn.
- AI: Google Gemini through the Google Gen AI SDK.
- Weather: Open-Meteo and MET Norway locationforecast; no weather API key is needed.
- Market prices: data.gov.in Agmarknet API; a free API key is optional for live prices.
- Speech: browser Web Speech API for speech input and speech synthesis for listening.
- Hosting: Vercel for the frontend and Render for the backend, using their free offerings.

## Run locally on Windows

Use two PowerShell terminals from the repository folder. Copy the example environment files before editing them.

### 1. Prepare and start the backend

```powershell
Set-Location "C:\Users\VAIBHAV JANGLE\Desktop\Kisan Mitra\backend"
Copy-Item .env.example .env
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
notepad .env
uvicorn main:app --reload
```

In `backend/.env`, add `GEMINI_API_KEY` for Gemini responses and optionally `DATA_GOV_API_KEY` for live mandi prices. Keep `ALLOWED_ORIGIN=http://localhost:5173` for local development. Open `http://localhost:8000/health`; the expected response is `{"status":"ok"}`. If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and activate the environment again.

### 2. Prepare and start the frontend

```powershell
Set-Location "C:\Users\VAIBHAV JANGLE\Desktop\Kisan Mitra\frontend"
Copy-Item .env.example .env
npm install
npm run dev
```

Open the localhost URL shown by Vite, usually `http://localhost:5173`. The frontend `.env` should have `VITE_API_URL=http://localhost:8000`. Restart Vite after changing that file. The app still provides fallback advice and sample mandi data when optional providers are unavailable.

## Deploy

### Render backend

1. Push the repository to GitHub and create a Render Web Service from it.
2. Set the root directory to `backend`, the build command to `pip install -r requirements.txt`, and the start command to `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Set `GEMINI_API_KEY`, `GEMINI_MODEL` (optional), `DATA_GOV_API_KEY` (optional), and `ALLOWED_ORIGIN` to the exact Vercel site origin.
4. Deploy and check `https://YOUR-RENDER-SERVICE.onrender.com/health`.

Backend URL: `https://YOUR-RENDER-SERVICE.onrender.com` (replace with your Render URL).

### Vercel frontend

1. Import the GitHub repository in Vercel and set the project root to `frontend` with the Vite preset.
2. Set `VITE_API_URL=https://YOUR-RENDER-SERVICE.onrender.com` in Vercel environment variables.
3. Deploy, then make sure Renderâ€™s `ALLOWED_ORIGIN` matches the final Vercel URL exactly.

Frontend URL: `https://YOUR-PROJECT.vercel.app` (replace with your Vercel URL).

Renderâ€™s free service may sleep when idle. A free UptimeRobot monitor can ping the backend `/health` route every five minutes, though it cannot guarantee instant wake-up.

## Limitations and responsible use

- District coverage currently focuses on Maharashtra; live market availability depends on Agmarknet data and its free API quota.
- Weather and AI services can be delayed, unavailable, or incomplete. Bundled sample mandi and weather data is labelled when used.
- Crop Doctor provides a possible visual diagnosis, not a confirmed diagnosis. AI advice can be wrong. Confirm treatment decisions and all pesticide or fertiliser dosages with your local Krishi Vigyan Kendra or agriculture officer.
- Voice input and speech output depend on browser and device language support.
- Render free instances may have cold starts. In-memory caches clear when the backend restarts.
- The app has no offline mode and no persistent backend storage.

## Future scope

- Opt-in WhatsApp alerts for useful weather or market changes.
- Expand district and state coverage with verified local data.
- Explore a useful offline mode for saved forecasts and guidance.

## Credits

Google Gemini Â· Open-Meteo Â· MET Norway Â· data.gov.in (Agmarknet) Â· Vercel Â· Render Â· Web Speech API Â· OpenAI Codex Â· Cloude

