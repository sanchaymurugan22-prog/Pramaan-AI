# Pramaan AI (प्रमाण) — project brief for Claude Code

"Content you can prove." Smart India Hackathon, Problem Statement 26154 (NTRO):
Gen AI Platform for Automated Content Transformation.

Read this whole file before doing any work. This project folder is `~/Documents/Pramaan AI/`. The project document and all 46 screen
designs are inside it (see "Reference material" at the bottom). The folder name has a space, so
always quote paths in shell commands, e.g. `cd ~/Documents/"Pramaan AI"`.

## What we are building (in one paragraph)
An app that runs fully offline on the organisation's own computer. An Operator uploads a source
(PDF, Word, text, scanned image, audio/video, or a prompt), the app runs a safety check, builds ONE
"fact sheet" from the source, then writes any of 7 outputs from that same fact sheet: Advisory
(CERT-In style), Executive summary, Presentation (+speaker notes), Video package (script,
storyboard, narration, subtitles), Infographic, LinkedIn post, X thread — in English and Indian
languages. Every sentence is traced to the source. A Reviewer approves and digitally signs outputs;
each signed file gets a QR code and an entry in a tamper-evident record book. A public
"Is this real?" page lets anyone verify a document or check a suspicious message.

## The person you are working with
- A student developer building this for a hackathon. Explain what you did in simple words.
- Build in small, working steps. After each step, tell them exactly how to run and test it.
- Never ask them to paste secrets (API keys, tokens, passwords) into chat. Secrets go in `.env`.

## Hard rules
1. **Offline-first.** The finished app must work with no internet. No CDN links, no Google Fonts
   URLs, no cloud databases (no Firebase). Fonts and libraries are bundled locally.
2. **AI provider switch.** All LLM calls go through ONE module (`backend/app/ai/llm.py`) that speaks
   the OpenAI-compatible chat API. Configured by `.env`:
   - `AI_MODE=local` → llama.cpp server at `LLM_BASE_URL` (default `http://localhost:8081/v1`),
     model Sarvam 30B (GGUF).
   - `AI_MODE=cloud` → Sarvam AI hosted API (development fallback only). Check docs.sarvam.ai for the
     current base URL, auth header and model names before writing this code; do not guess.
   The rest of the code must not know which one is in use.
3. **Secrets:** read from `.env` only. `.env` is in `.gitignore`. Keep `.env.example` up to date
   with names only, never real values.
4. **Never commit** model files (`*.gguf`, `models/`), user data (`data/`), `.env`, `node_modules/`,
   `.venv/`.
5. **Grounding is mandatory.** Every generated sentence must be linkable to a source span, or be
   flagged as "not found in source". Never silently drop this.
6. **MVP first.** Build the stage you are asked for. Do not add features from later stages.
7. Prefer simple, readable code with comments over clever code.

## Machine constraints (important)
- Developer laptop: MacBook Pro 2017, **Intel** Core i7 (x64), **16 GB RAM**, macOS Ventura 13.7,
  no usable GPU. Homebrew is NOT available (no Intel support). Tools were installed manually:
  Python 3.12 (python.org), Node LTS (nodejs.org), git (Xcode CLT), llama.cpp prebuilt macOS-x64
  binary in `~/llama`.
- Sarvam 30B Q4 GGUF (~20 GB) is larger than RAM, so it will be slow here. Keep prompts short,
  context small (`-c 4096`), reuse the fact sheet (prompt caching), stream output, and generate
  short outputs first. Make `max_tokens` configurable per output type.
- Recent PyTorch versions do not ship Intel-macOS wheels. For AI4Bharat models (Stage 8) prefer
  ONNX / CTranslate2 builds or a pinned older torch; decide at Stage 8, not before.

## Tech stack
| Part | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| Database | SQLite via SQLAlchemy 2.0 (single file `data/pramaan.db`). Encryption with SQLCipher is added in Stage 6 behind the same `db.py` module. |
| Frontend | React + TypeScript + Vite. Plain CSS with design tokens as CSS variables (see Design). |
| LLM runtime | llama.cpp `llama-server` (OpenAI-compatible API) |
| Documents in | pypdf / pdfplumber, python-docx, Tesseract OCR (later), speech-to-text (later) |
| Documents out | python-pptx, python-docx, PDF (ReportLab or WeasyPrint), Pillow/HTML render for PNG, SRT text |
| Signing | SHA-256 fingerprints, hash-chained record book, `cryptography` (test key now; DSC via PKCS#11 later), `qrcode` |
| Public verify page | Static HTML + JS (Web Crypto), no backend, in `verify-page/` |

## Folder structure (create as needed)
```
Pramaan AI/   (project root)
  CLAUDE.md  README.md  .gitignore  .env.example
  Designs/  Pramaan AI - Project Document.docx/.pdf   (reference only, do not edit)
  backend/
    app/
      main.py            FastAPI app, routes mounted here
      config.py          reads .env
      db.py              engine, session, models
      ai/llm.py          the ONE place that talks to the LLM
      ai/prompts/        one prompt template file per output type + factsheet.md
      pipeline/          ingest.py, safety.py, factsheet.py, generate.py, checks.py
      exporters/         pptx.py, docx.py, pdf.py, infographic.py, srt.py
      signing/           records.py (hash chain), qr.py
      routes/            auth.py, jobs.py, outputs.py, review.py, admin.py, verify.py
    tests/
    requirements.txt
  frontend/              React app (screens from the designs)
  verify-page/           public "Is this real?" static site
  scripts/               start.sh, install.sh (later)
  models/                GGUF files (git-ignored)
  data/                  database + uploads + outputs (git-ignored)
  samples/               public sample reports for testing (e.g. a public CERT-In advisory)
```

## Core data model (first version)
- users(id, name, employee_id, email, role[operator|reviewer|admin], password_hash, is_active, dsc_holder)
- jobs(id, title, owner_id, status[draft|generating|ready|in_review|sent_back|approved], tlp[RED|AMBER|GREEN|CLEAR], version, created_at)
- sources(id, job_id, filename, kind, sha256, text_path, pages)
- fact_sheets(id, job_id, json)   # facts: [{id, text, source_id, page, quote}]
- outputs(id, job_id, type, language, content_json, quality_json, status)
- reviews(id, job_id, reviewer_id, decision, comments_json, created_at)
- records(seq, job_id, output_id, sha256, signer, signed_at, prev_hash, entry_hash)   # record book
- audit_log(seq, actor, action, detail, created_at, prev_hash, entry_hash)

## How generation works (keep this design)
1. Ingest → plain text per source with page numbers.
2. Safety scan (regex + word lists): classification words, Aadhaar, PAN, phone, email, IPs,
   keys/passwords, and prompt-injection phrases. Suggest TLP.
3. Fact sheet: ONE LLM call → strict JSON: summary, key_facts[{text, source_id, page, quote}],
   entities, severity, dates, indicators (CVE/IP/hash), recommended_actions.
4. Generate each selected output from the fact sheet (not from the raw source) using its own
   prompt template and JSON schema. Settings: audience, tone, objective, style, detail, language.
   Public outputs (LinkedIn, X, infographic) get sensitive values masked.
5. Checks: map each output sentence to fact ids / source quotes; flag unsupported sentences;
   compare numbers/dates across outputs; score quality.
6. Review → sign → record book → QR → export.

## Design (match the designs exactly)
Tricolour palette. Role colours: Operator = saffron, Reviewer = green, Admin = navy.
```
--saffron:#F28C28; --saffron-dark:#A34A00; --saffron-light:#FFF4E8; --saffron-mid:#FFDDB8;
--green:#138808;   --green-dark:#0E6A06;   --green-light:#EBF7E7;   --green-mid:#C9EBC1;
--navy:#1E2F8F;    --navy-dark:#15206B;    --navy-light:#EEF0FB;    --navy-mid:#D2D8F4;
--ink:#1B1D26; --muted:#555B6B; --bg:#FBF8F2; --card:#FFFFFF; --line:#EFE7D9; --line-2:#E2D8C6;
--red:#C0392B; --red-dark:#A3261B; --red-light:#FDEDEA; --yellow:#FCE68A; --yellow-light:#FFF8DB;
```
Fonts (bundle locally, OFL licence): Poppins (headings), Hind (body), Rozha One (brand name only),
IBM Plex Mono (codes/hashes), Noto Sans for other Indian scripts. Cards: white, 18px radius,
1px border `--line`. Buttons 44px min height, 12px radius. Thin tricolour strip at the top of pages.
Logo: navy seal with a saffron→white→green tick.

## Build stages (do only the stage you are asked for)
- Stage 2 Skeleton: folders, backend "hello" API + health check, frontend shell with the design
  tokens and sidebar, `.gitignore`, `.env.example`, README with run steps, git init + first commit.
- Stage 3 Core engine: upload text/PDF → fact sheet → 7 outputs as JSON, shown on a simple page.
- Stage 4 Real files: PPTX, DOCX, PDF, infographic PNG, SRT.
- Stage 5 Trust: sentence→source tracing, yellow warnings, cross-output fact match, quality score.
- Stage 6 Security: safety scanner UI, TLP, masking, prompt-injection shield, SQLCipher, roles/login.
- Stage 7 Anti-fake: signing, record book, QR, verify page, "Is this real?" message checker.
- Stage 8 Languages & voice: IndicTrans2, Indian TTS, speech-to-text.
- Stage 9 All screens from the designs, for all roles.
- Stage 10 Submission: README, 2-page architecture doc, demo script, 5-slide deck.

## Reference material (on this Mac)
- Project document: `./Pramaan AI - Project Document.docx` (and .pdf)
- Screen designs (images): `./Designs/Screen images/`
- Clickable prototype (HTML): `./Designs/Clickable prototype (open index.html)/`
  When building a screen, open the matching HTML file and copy its layout, spacing and colours.
