# Pramaan AI (प्रमाण) — Content you can prove.

Offline, Indian-AI platform that turns one source into advisories, summaries, slides, video
packages, infographics and social posts in Indian languages, with every line traced to its source
and every document signed and verifiable.

Smart India Hackathon · Problem Statement 26154 · NTRO.

**Current stage: 5 — Trust.** Paste text or upload a .txt / .pdf / .docx, and the app builds
one fact sheet from it, then writes any of 7 outputs from that fact sheet. Every sentence of every
output is linked to the fact it uses, and one click shows that fact's quote highlighted in the
source. Sentences with no fact, and numbers or dates that are not in the source, are flagged; a
consistency check makes sure every output uses the same numbers; each output gets a quality score.
The operator can edit an output (the checks run again, old versions are kept) or regenerate just
one output. Every finished output can be downloaded as a real file (Word, PDF, PowerPoint, PNG,
subtitles, text), or all together as one campaign kit (.zip). See `CLAUDE.md` for the full plan.

## What you need (already installed on the dev Mac)

- Python 3.12 (python.org)
- Node LTS (nodejs.org)
- git (Xcode command-line tools)
- llama.cpp prebuilt binary in `~/llama` (only needed to talk to the AI)

## First-time setup

(If you set up an earlier stage, run the `pip install` line again: Stage 4 added python-pptx,
ReportLab and Pillow. Stage 5 adds no new packages. Its new database columns and the
`output_versions` table are added to your existing `data/pramaan.db` automatically when the
backend starts; nothing is deleted.)

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
6. Click any sentence: the **Source trace** panel on the right shows the fact it uses and the quote
   highlighted in the source. (See "Trust" below for everything else to try.)
7. Under each output, click a **Download** button; at the top, **Download campaign kit (.zip)**.

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
  → checks        (no AI) every sentence linked to a fact; values not in the source flagged;
                  the same numbers in every output; a 0-100 quality score (Stage 5)
  → edit / regenerate one output → checks again; every version kept
```

- `backend/app/ai/llm.py` is the only file that talks to the model. In local mode it sends the
  JSON shape to llama.cpp, which then *forces* valid JSON; it streams the answer (so long answers
  don't time out and progress can be shown). If a server can't do that, it finds the JSON in the
  reply and retries once. If an answer is cut off at the token limit, it keeps what was written.
- Token limits per output are in `.env` (`MAX_TOKENS_...`); "Short" detail uses 75% of them.
- The fact sheet keeps at most 8 key facts per model answer and may write up to 1400 tokens
  (`MAX_TOKENS_FACTSHEET`), so it finishes cleanly instead of being cut off.
- Jobs run in the background, one at a time. If the backend restarts, unfinished jobs carry on.

## Downloads (Stage 4)

Files are made from the outputs already saved in the database — no AI call, so they take about a
second even on the slow laptop. They are made again on every download (so they always match the
output) and saved under `data/jobs/<id>/exports/`.

| Output | Files |
|---|---|
| Advisory, Executive summary | `.pdf` and `.docx` |
| Presentation | `.pptx` — title slide, one slide per generated slide, closing slide; speaker notes on every slide |
| Infographic | `.png`, 1080 × 1350, drawn in the layout the AI suggested (number grid, vertical steps or timeline); previewed on the Results page |
| Video package | `.docx` (script and storyboard) and `.srt` (subtitles) |
| LinkedIn post, X thread | `.txt` (the thread is numbered 1/4, 2/4 …) |
| Campaign kit | one `.zip` with every file of every finished output, plus `README.txt` listing each file's SHA-256 fingerprint |

Every file carries the job title, the date, the footer **"AI-assisted · pending human approval"**,
the TLP label when one is set (Stage 6 sets it), and an empty box where the QR code goes once a
reviewer signs it (Stage 7). Fact ids (F1, A2 …) are kept out of the files; they stay in the JSON.
An `.srt` file can only hold subtitles, so its labels are one extra subtitle after the narration.

**Fonts.** Poppins, Hind and IBM Plex Mono (all OFL, licences included) are bundled in
`backend/app/assets/fonts/`. PDF and PNG files carry the fonts inside them. Word and PowerPoint
files only *name* the font, so for the exact look install the fonts once on the computer that opens
them: double-click each `.ttf` file in that folder and click **Install Font**. Without them, Pages /
Keynote / Word use a similar font; nothing else changes. Indian-script fonts are added in Stage 8
(see `backend/app/exporters/fonts.py`).

The exporters are in `backend/app/exporters/`: `blocks.py` (the sections of each document, shared
by Word and PDF), `docx.py`, `pdf.py`, `pptx.py`, `infographic.py`, `srt.py`, `text.py`, `kit.py`.

## Trust (Stage 5)

Everything here is done by rules in code, with **no AI call**, so it is instant and runs again
after every edit. The code is in `backend/app/pipeline/`: `trace.py` (finding text in the source),
`values.py` (numbers, dates, CVEs, IPs, hashes), `segments.py` (the text fields of each output),
`checks.py` (sentences, links, score, consistency) and `versions.py`.

**The Results page** now follows the design *13 · Results · Advisory with source trace*: a tab per
output (with its score), the output on the left, and on the right the **Source trace**, the
warnings and the **Quality score**. On a narrow window the Source trace opens at the bottom.

| Feature | What you see | How it works |
|---|---|---|
| Source trace | Click a sentence or a chip (F3, A1, D2): the fact, its source (S1), page, *Found / Close match / Not found*, and the source page with the quote in **yellow**, scrolled into view | Each fact's quote (and each action and date) is found in the source word by word when the fact sheet is built, and its character positions are saved (`start`, `end`) |
| Sentence links | Small chips after every sentence show which facts it uses | Each text field is split into sentences; a sentence must share meaning words with the fact the AI cited, otherwise the best matching fact is used ("matched by its words") |
| Not linked to a fact | **Yellow underline** and a yellow card listing them | No fact fits the sentence (e.g. an opinion the AI added) |
| Not in source | **Red wavy underline** on the value, red card | Every number, date, CVE id, IP address and file hash in an output must also be in the fact sheet or the source. `1.2 million` = `1,200,000`, `five` = `5`, `22 Sep` = `22 September` |
| Consistency | Panel at the top: "All outputs agree", or each mismatch ("the fact sheet says 42 hospitals, but the X thread says 43 hospitals") with a button that opens that sentence | Numbers are compared with their unit word (42 *hospitals*, 72 *hours*) against the fact each sentence is linked to |
| Quality score | Badge on each tab and on the job; hover (or Tab to it) for the explanation in plain words; the card shows the parts | 40 points: sentences linked · 25: quotes found in the source (close = half) · 20: values in the source (each missing one costs a third) · 15: length and format rules (X 280 characters, LinkedIn 3,000, slides 15 words a point, narration 40 words a scene, not cut off …). Job score = average. Saved in the database |
| Edit | **Edit** → a box per text field → **Save and re-check** | Saved as a new version "Edited by human"; all checks run again; empty a box to remove that item; video subtitles are re-timed |
| Versions | **Versions** → **View** an older one (read only, with its own score) | Table `output_versions`; nothing is ever overwritten |
| Regenerate | **Regenerate** writes only that output again from the same fact sheet | Uses the AI (local / cloud); mock mode returns the same canned text as a new version. If the AI fails, the previous version stays |

Downloads and the campaign kit always use the **latest** version.

Export fixes in this stage: the PowerPoint footer is measured with the real Hind font and a long
job title is shortened with "…" so the footer stays on one line; in the PDF the indicator table's
value column is wider (and codes shrink a little if still needed), so a SHA-256 fingerprint stays
on one line.

## API (see <http://localhost:8000/docs> for all details)

| Call | What it does |
|---|---|
| `GET /api/options` | the 7 output types and the setting choices |
| `POST /api/jobs` | create a job: form fields `text` and/or `files`, `outputs` (repeat per output), `title`, `audience`, `tone`, `objective`, `style`, `detail_level` |
| `GET /api/jobs` | list jobs |
| `GET /api/jobs/{id}` | status, current step, fact sheet, each output as it finishes, its checks (`quality`), score, version, and the job's `consistency` and `quality_score` |
| `GET /api/jobs/{id}/sources/{S1}` | the text of one source, page by page (the fact sheet's `start`/`end` are positions in these pages) |
| `PUT /api/jobs/{id}/outputs/{output_id}` | save edits as a new version: JSON `{"fields": [{"path": ["tweets", 0, "text"], "text": "..."}]}` (the editable paths are in each output's `fields`) |
| `POST /api/jobs/{id}/outputs/{output_id}/regenerate` | write one output again from the same fact sheet |
| `GET /api/jobs/{id}/outputs/{output_id}/versions` | every version (number, who made it, score, time); add `/{n}` for one version's text and checks |
| `POST /api/jobs/{id}/retry` | run the failed parts of a job again |
| `GET /api/jobs/{id}/outputs/{output_id}/download?format=pdf` | one file: `docx`, `pdf`, `pptx`, `png`, `srt` or `txt` (each output lists its `formats`); add `&inline=true` to view instead of save |
| `GET /api/jobs/{id}/kit.zip` | the campaign kit: every finished output in one .zip |

Example with curl (from the project folder):

```bash
curl -F files=@samples/sample-ransomware-report.txt -F outputs=x_thread -F outputs=linkedin_post http://localhost:8000/api/jobs
```

Download job 1's campaign kit into the current folder:

```bash
curl -OJ http://localhost:8000/api/jobs/1/kit.zip
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
  app/pipeline/   ingest.py, factsheet.py, generate.py, checks.py, output_types.py, runner.py,
                  trace.py, values.py, segments.py, versions.py (Stage 5 checks and versions)
  app/exporters/  real files: docx.py, pdf.py, pptx.py, infographic.py, srt.py, text.py, kit.py
  app/assets/fonts/  Poppins, Hind, IBM Plex Mono (TTF, OFL)
  app/routes/     system.py (health, AI ping), jobs.py (jobs API), outputs.py (edit, regenerate, versions, downloads)
frontend/       React + TypeScript + Vite app; design tokens in src/styles/tokens.css
verify-page/    public "Is this real?" page (Stage 7)
scripts/        start.sh (app), start-ai.sh (AI model)
samples/        sample reports for testing (sample-ransomware-report.txt is fictional)
models/, data/  model files and app data (never committed)
Designs/        screen designs and clickable prototype (reference only)
```
