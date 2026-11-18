# AGENTS.md

Project: Kisan Mitra (hackathon web app). Full requirements are in `spec.md` at the repository root. Read it completely before making changes.

## Rules
- Follow `spec.md` exactly. Do not add features outside it.
- Free tools only (Gemini free tier, Open-Meteo, data.gov.in, Vercel, Render). No paid services.
- Never hardcode API keys. Use `.env` files, keep `.env` in `.gitignore`, and provide `.env.example` files.
- The owner is a beginner on Windows (PowerShell, VS Code). Give simple, copy-paste, PowerShell-compatible commands and say what output to expect.
- The site must be fully responsive: bottom tab bar under 768px; sidebar plus centered 2-column layout at 768px and above. Verify at 360, 390, 768, 1024 and 1440 px and fix overflow, cut-off text and small tap targets.
- Test everything you build (all endpoints, all three languages, failure fallbacks) and report results honestly, including anything you could not verify.
- Keep the backend in `backend/` (FastAPI, Render) and the frontend in `frontend/` (React + Vite + Tailwind, Vercel).
