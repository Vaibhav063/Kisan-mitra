# Kisan Mitra 🌱

A free, multilingual farm companion for Maharashtra. Kisan Mitra combines seven-day Open-Meteo forecasts, Agmarknet mandi prices and Gemini responses, with local rule-based advice and sample mandi prices when services are unavailable. Preferences stay in this browser's local storage; there are no accounts or database.

## What you need

- Windows 10/11, PowerShell, VS Code
- Python 3.11 (the API is also compatible with newer Python versions)
- Node.js LTS and npm
- Optional free keys: Google Gemini API key from Google AI Studio, and data.gov.in API key. No key is needed for Open-Meteo.

## Run locally (PowerShell)

Open two PowerShell terminals in the project folder.

### Backend terminal

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

In `.env`, add your optional keys to `GEMINI_API_KEY` and `DATA_GOV_API_KEY`. Keep `ALLOWED_ORIGIN=http://localhost:5173`. Expected output includes `Uvicorn running on http://127.0.0.1:8000`. Check `http://localhost:8000/health` for `{"status":"ok"}`. If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.

### Frontend terminal

```powershell
Set-Location "C:\Users\VAIBHAV JANGLE\Desktop\Kisan Mitra\frontend"
Copy-Item .env.example .env
npm install
npm run dev
```

Open the localhost URL printed by Vite (usually `http://localhost:5173`). If you change `.env`, restart Vite. Without a Gemini key, advice and Ask still return rule-based responses. Without a data.gov.in key or live results, the mandi screen clearly labels sample data.

## API routes

- `GET /health`
- `GET /api/districts`
- `GET /api/weather?district=beed`
- `GET /api/mandi?district=beed&crop=Soybean`
- `POST /api/advice` with `{"district":"beed","crop":"Soybean","language":"mr"}`
- `POST /api/ask` with the same fields plus `"question":"आज फवारणी करू का?"`

Interactive API documentation is at `http://localhost:8000/docs` while the backend runs.

## Deploy

### Render backend

1. Push this repository to GitHub. Keep `.env` files out of Git; `.gitignore` already excludes them.
2. In Render, create a **Web Service** from the repository. Set root directory to `backend`, build command to `pip install -r requirements.txt`, start command to `uvicorn main:app --host 0.0.0.0 --port $PORT`, and select the free instance type.
3. Add environment variables in Render: `GEMINI_API_KEY`, `GEMINI_MODEL` (optional; default `gemini-2.0-flash`), `DATA_GOV_API_KEY`, and `ALLOWED_ORIGIN` set to the exact Vercel site origin, such as `https://your-project.vercel.app`.
4. Deploy. Check `https://YOUR-SERVICE.onrender.com/health` returns `{"status":"ok"}`. Render free services may sleep and take time to wake.

### Vercel frontend

1. Import the same GitHub repository into Vercel and set the project root directory to `frontend` with the Vite framework preset.
2. Add `VITE_API_URL=https://YOUR-SERVICE.onrender.com` (no trailing slash) in Vercel environment variables.
3. Deploy, then update Render's `ALLOWED_ORIGIN` to the final Vercel origin and redeploy the backend if needed.
4. Confirm both public links work without signing into the app. A Vercel preview domain needs to be explicitly allowed by the backend CORS origin.

### Keep Render awake

Create a free UptimeRobot HTTP(s) monitor for `https://YOUR-SERVICE.onrender.com/health` with a 5-minute interval. UptimeRobot can reduce cold starts but cannot guarantee instant availability.

## Keys and privacy

- Backend keys go only in `backend/.env` for local use and Render environment variables for deployment.
- `frontend/.env` contains only `VITE_API_URL`, which is a public backend address, never a secret.
- Do not commit either `.env` file. `.env.example` files contain blank key fields.
- The app stores language, district and crop in local storage. It does not collect personal details or use analytics.

## Credits

Google Gemini · Open-Meteo · data.gov.in (Agmarknet) · Vercel · Render · Web Speech API

AI responses can be wrong. Follow local agriculture officer guidance for serious crop issues and all pesticide/fertiliser dosages.
