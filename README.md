# Pramaan AI (प्रमाण) — Content you can prove.

Offline, Indian-AI platform that turns one source into advisories, summaries, slides, video
packages, infographics and social posts in Indian languages, with every line traced to its source
and every document signed and verifiable.

Smart India Hackathon · Problem Statement 26154 · NTRO.

**Current stage: 3 — Core engine.** Paste text or upload a .txt / .pdf / .docx, and the app builds
one fact sheet from it, then writes any of 7 outputs from that fact sheet, each linked back to the
facts it uses. See `CLAUDE.md` for the full plan.

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

## Try it quickly with the mock AI (no model needed)

The mock AI answers instantly with ready-made answers written for the sample report. Use it to
check the screens without waiting for the real model.

1. In `.env`, set `AI_MODE=mock` (optionally `MOCK_DELAY_SECONDS=3` to see the progress display).
2. Start the app: `./scripts/start.sh` (no need for `start-ai.sh`).
3. Open <http://localhost:5173>, click **New transformation**.
4. Click **Choose files** and pick `samples/sample-ransomware-report.txt` (or paste its text).
5. Tick some outputs, click **Generate**. The Results page shows the fact sheet, then each output.

Set `AI_MODE=local` again (and restart `start.sh`) to use the real model.

## Try it with the real local AI

The real model is slow on the dev laptop (about 1.4 tokens a second), so start small:

1. `.env`: `AI_MODE=local`. Terminal 1: `./scripts/start-ai.sh`. Terminal 2: `./scripts/start.sh`.
2. **New transformation** → choose `samples/sample-ransomware-report.txt` → tick only
   **X thread** and **LinkedIn post** (the default) → **Generate**.
3. Measured on the dev laptop with the sample report: fact sheet about 11 minutes (the model first
   reads the whole report, then writes the facts), X thread about 7 minutes, LinkedIn post about
   5 minutes — roughly 25 minutes in total. The page shows what is happening
   and how many tokens have been written. You can leave the page and come back via **My jobs**.

If something fails (for example llama-server was not running), start the model and click
**Try again** on the Results page: finished parts are kept, only the rest is redone.

## How it works

```
source (text / .txt / .pdf / .docx)
  → ingest        plain text per page, saved under data/jobs/<id>/sources/
  → fact sheet    ONE model call per chunk (long sources are split to fit the 4096-token context),
                  merged; each fact has a quote that is checked against the source;
                  IPs, CVEs and file hashes are found by exact patterns, not by the model
  → outputs       each written FROM THE FACT SHEET with its own prompt (backend/app/ai/prompts/)
                  and JSON shape; short outputs first; every part lists the fact ids it uses
  → checks        parts not linked to any fact are flagged in yellow (never silently dropped)
```

- `backend/app/ai/llm.py` is the only file that talks to the model. In local mode it sends the
  JSON shape to llama.cpp, which then *forces* valid JSON; it streams the answer (so long answers
  don't time out and progress can be shown). If a server can't do that, it finds the JSON in the
  reply and retries once. If an answer is cut off at the token limit, it keeps what was written.
- Token limits per output are in `.env` (`MAX_TOKENS_...`); "Short" detail uses 75% of them.
- Jobs run in the background, one at a time. If the backend restarts, unfinished jobs carry on.

## API (see <http://localhost:8000/docs> for all details)

| Call | What it does |
|---|---|
| `GET /api/options` | the 7 output types and the setting choices |
| `POST /api/jobs` | create a job: form fields `text` and/or `files`, `outputs` (repeat per output), `title`, `audience`, `tone`, `objective`, `style`, `detail_level` |
| `GET /api/jobs` | list jobs |
| `GET /api/jobs/{id}` | status, current step, fact sheet, and each output as it finishes |
| `POST /api/jobs/{id}/retry` | run the failed parts of a job again |

Example with curl (from the project folder):

```bash
curl -F files=@samples/sample-ransomware-report.txt -F outputs=x_thread -F outputs=linkedin_post http://localhost:8000/api/jobs
```

## About the AI model

The app works without the model; the dashboard's **Test AI** button then shows a friendly
"llama-server is not running" message.

`scripts/start-ai.sh` runs:

```
llama-server -hf sarvamai/sarvam-30b-gguf:Q4_K_M --offline --port 8081 -c 4096 -t 4 -np 1 -b 512 --reasoning-budget 0
```

- `--offline` uses the copy already downloaded to `~/.cache/huggingface` and never goes online.
  On a new computer, download the model (~20 GB) once by running the same command without
  `--offline`.
- `-b 512` makes the server report progress while it reads a long prompt (this takes minutes on
  the laptop), which also stops the backend from giving up while it waits.
- `--reasoning-budget 0` turns off Sarvam 30B's "thinking", so answers start straight away.
  `backend/app/ai/llm.py` also switches thinking off for each request.
- It is slow on the dev Intel Mac (about 1.4 tokens per second), so the backend waits up to
  `LLM_TIMEOUT_SECONDS` (600 seconds by default, set in `.env`) for the next part of a reply.

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

Backend tests (they always use the mock AI and a temporary folder, so no model is needed and
your `data/` folder is not touched):

```bash
cd backend && .venv/bin/python -m pytest
```

## AI provider switch

Set `AI_MODE` in `.env`:

- `local` — llama.cpp on this computer (default, offline).
- `mock` — no model; instant ready-made answers, for testing the screens.
- `cloud` — Sarvam hosted API, for development only. Put your key in `SARVAM_API_KEY` in `.env`
  (never in code or chat). The hosted API no longer offers `sarvam-30b`; it uses `sarvam-105b`.

Restart the app after changing `.env`.

## Folder map

```
backend/        FastAPI app (app/main.py), settings (app/config.py), database (app/db.py)
  app/ai/         llm.py (the only file that talks to the model), prompts/*.md, mock answers
  app/pipeline/   ingest.py, factsheet.py, generate.py, checks.py, output_types.py, runner.py
  app/routes/     system.py (health, AI ping), jobs.py (jobs API)
frontend/       React + TypeScript + Vite app; design tokens in src/styles/tokens.css
verify-page/    public "Is this real?" page (Stage 7)
scripts/        start.sh (app), start-ai.sh (AI model)
samples/        sample reports for testing (sample-ransomware-report.txt is fictional)
models/, data/  model files and app data (never committed)
Designs/        screen designs and clickable prototype (reference only)
```
