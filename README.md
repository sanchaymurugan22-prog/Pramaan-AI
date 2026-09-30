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

Use two terminals, both in the project folder (`cd ~/Documents/"Pramaan AI"`).

**Terminal 1: the AI model** (Sarvam 30B on port 8081):

```bash
./scripts/start-ai.sh
```

Wait until it prints that the server is listening (loading the model can take a few minutes).

**Terminal 2: the app** (backend on port 8000 + frontend on port 5173):

```bash
./scripts/start.sh
```

Then open <http://localhost:5173>. Press **Ctrl+C** in each terminal to stop.

| Part | Address |
|---|---|
| Frontend (the app) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (auto-generated) | http://localhost:8000/docs |
| AI model (llama-server) | http://localhost:8081 |

## About the AI model

The app works without the model; the dashboard's **Test AI** button then shows a friendly
"llama-server is not running" message.

`scripts/start-ai.sh` runs:

```
llama-server -hf sarvamai/sarvam-30b-gguf:Q4_K_M --offline --port 8081 -c 4096 -t 4 -np 1 --reasoning-budget 0
```

- `--offline` uses the copy already downloaded to `~/.cache/huggingface` and never goes online.
  On a new computer, download the model (~20 GB) once by running the same command without
  `--offline`.
- `--reasoning-budget 0` turns off Sarvam 30B's "thinking", so answers start straight away.
  `backend/app/ai/llm.py` also switches thinking off for each request.
- It is slow on the dev Intel Mac (about 1.4 tokens per second), so the backend waits up to
  `LLM_TIMEOUT_SECONDS` (600 seconds by default, set in `.env`) for a reply.

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
scripts/        start.sh (app), start-ai.sh (AI model)
samples/        public sample reports for testing
models/, data/  model files and app data (never committed)
Designs/        screen designs and clickable prototype (reference only)
```
