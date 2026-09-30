# Pramaan AI (प्रमाण) — Content you can prove.

Offline, Indian-AI platform that turns one source into advisories, summaries, slides, video
packages, infographics and social posts in Indian languages, with every line traced to its source
and every document signed and verifiable.

Smart India Hackathon · Problem Statement 26154 · NTRO.

**Current stage: 2 — Skeleton.** Backend health check + AI ping, and the Operator dashboard shell.
See `CLAUDE.md` for the full plan.

## What you need (already installed on the dev Mac)

- Python 3.12 (python.org)
- Node LTS (nodejs.org)
- git (Xcode command-line tools)
- llama.cpp prebuilt binary in `~/llama` (only needed to talk to the AI)

## First-time setup

Run these from the project folder (`cd ~/Documents/"Pramaan AI"`):

```bash
cp .env.example .env
```

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
```

```bash
cd frontend && npm install && cd ..
```

## Run the app

```bash
./scripts/start.sh
```

Then open <http://localhost:5173>. Press **Ctrl+C** in that terminal to stop both servers.

| Part | Address |
|---|---|
| Frontend (the app) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (auto-generated) | http://localhost:8000/docs |
| AI model (llama-server) | http://localhost:8081 |

## Start the AI model (separate terminal)

The app works without the model; the dashboard's **Test AI** button then shows a friendly
"llama-server is not running" message. To start Sarvam 30B locally:

```bash
~/llama/llama-server -hf sarvamai/sarvam-30b-gguf:Q4_K_M --port 8081 -c 4096 -t 4
```

The first run downloads the model (~20 GB) into `~/.cache/huggingface`; after that it runs offline.
If you have the GGUF file in `models/` instead, use `-m models/<file>.gguf` in place of `-hf ...`.
It is slow on the dev laptop (about 4 words per second), so the first reply can take a minute.

Sarvam 30B is a "thinking" model. `backend/app/ai/llm.py` switches thinking off by default so short
answers come back quickly.

## Test it

```bash
curl http://localhost:8000/api/health
```

Expected: `{"status":"ok","ai_mode":"local"}`

```bash
curl http://localhost:8000/api/ai/ping
```

Expected with the model running: `{"ok":true,"reply":"Namaste.",...}`; without it:
`{"ok":false,"error":"Could not reach the local AI server ..."}`

Backend unit tests:

```bash
cd backend && .venv/bin/python -m pytest
```

## AI provider switch

Set `AI_MODE` in `.env`:

- `local` — llama.cpp on this computer (default, offline).
- `cloud` — Sarvam hosted API, for development only. Put your key in `SARVAM_API_KEY` in `.env`
  (never in code or chat). The hosted API no longer offers `sarvam-30b`; it uses `sarvam-105b`.

Restart the app after changing `.env`.

## Folder map

```
backend/        FastAPI app (app/main.py), settings (app/config.py), LLM module (app/ai/llm.py)
frontend/       React + TypeScript + Vite app; design tokens in src/styles/tokens.css
verify-page/    public "Is this real?" page (Stage 7)
scripts/        start.sh
samples/        public sample reports for testing
models/, data/  model files and app data (never committed)
Designs/        screen designs and clickable prototype (reference only)
```
