# Pramaan AI (प्रमाण) — Content you can prove.

**One report in, every format out, and every line traceable to its source.** Pramaan AI turns one
source — a threat report, an advisory, a policy note — into an advisory, an executive summary, a slide
deck, a video package, an infographic, a LinkedIn post and an X thread. It runs **entirely offline on
the organisation's own computer** with an Indian AI model (Sarvam 30B). Every sentence it writes is
linked to the place in the source it came from; a Reviewer approves and digitally signs the result; and
anyone can check a document or a forwarded message on a public **"Is this real?"** page.

Smart India Hackathon 2026 · Problem Statement **26154** (NTRO) · Gen AI Platform for Automated Content
Transformation.

| Read next | |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it is built: diagram, data flow, security model, offline design, scaling |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | The 2-minute demo, step by step |
| [docs/TEST_REPORT.md](docs/TEST_REPORT.md) | Every feature, how it was tested, and real Sarvam 30B speed |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | The detailed guide to every screen, check and API call |

## Features

**Writing**
- **One fact sheet, seven outputs.** The AI reads the source once into a fact sheet (facts, each with
  its quote and page; dates; recommended actions; CVEs, IPs and file hashes found by exact patterns).
  Every output is written from that fact sheet, so all outputs agree.
- **Seven outputs as real files:** CERT-In style advisory (PDF, Word), executive summary (PDF, Word),
  presentation with speaker notes (PowerPoint), video package (script and storyboard in Word, subtitles
  as .srt), infographic (PNG), LinkedIn post and X thread (text). All together as one campaign kit (.zip).
- Settings per job: audience, tone, objective, style, level of detail.
- **Emergency alert:** a short public alert with a live public-release check (no panic wording, no
  private data, SMS length), sent straight to the on-duty Reviewers for fast-track approval.
- **Watch folder:** reports dropped in a folder become drafts that wait for a person at the Safety check.

**Trust**
- **Source trace:** click any sentence to see the fact it uses and the quote highlighted in the source.
- Sentences not linked to a fact are marked in yellow; numbers, dates or names not in the source in red.
- Consistency check across outputs, a 0–100 quality score per output, every version kept, version compare.

**Safety**
- Before any AI reads a source, a rule-based scanner finds Aadhaar, PAN, phone numbers, emails, bank
  details, passports, vehicle numbers, GPS, internal IPs and hosts, passwords and keys, classification
  markings, and **hidden instructions** aimed at the AI (prompt injection, hidden text, hidden characters).
- The Operator chooses what to hide and a **TLP sharing label**; hidden values become placeholders
  (`[PHONE-1]`) before the AI, public outputs show `[phone number]`, and a leak check blocks any file
  that still contains a hidden value. TLP:RED / AMBER switch public outputs off.

**Accountability**
- Three roles (Operator, Reviewer, Admin), checked by the backend on every request; separation of duties
  (nobody reviews their own work); comments on single sentences; send back with reasons.
- **Signing:** approval signs every file (ECDSA P-256), adds a QR code and a record number, and writes a
  hash-chained **record book** entry. Records can be withdrawn, never deleted.
- **Public "Is this real?" page** (static, works offline, English and Hindi): check a record by QR code,
  a file by its fingerprint, or a pasted WhatsApp / SMS message for changes and scam signs.
- Hash-chained **audit trail** of every action; **encrypted** database (SQLCipher) and files (AES-256-GCM).

**Running an office**
- Admin overview, users and access requests, AI models and measured speed, letterhead (office name and
  logo on every file), security policies, record book, public page update, encrypted backups.
- In-app notifications, search across jobs, sources and records, Profile & settings (language, text size,
  high contrast), Help. Keyboard and screen-reader friendly (WCAG 2.1 AA / GIGW), works at 200% zoom.

## Screenshots

The screen designs are in [`Designs/Screen images/`](Designs/Screen%20images/) (46 screens) and the
clickable prototype in `Designs/Clickable prototype (open index.html)/`. The app follows them. For the
submission, take these screenshots of the running app (mock mode, demo data from the
[demo script](docs/DEMO_SCRIPT.md)):

| # | Screen | Address | Design |
|---|---|---|---|
| 1 | Splash | `#/welcome` | 01 Splash screen |
| 2 | Operator dashboard | `#/` | 08 Operator dashboard |
| 3 | Safety check with findings (sample-private-data.txt) | `#/new/<id>/safety` | 10 Safety check |
| 4 | Live progress | `#/jobs/<id>/progress` | 12 Generating |
| 5 | Advisory with source trace (a sentence clicked) | `#/jobs/<id>` | 13 Results · Advisory |
| 6 | Presentation viewer | `#/jobs/<id>` → Presentation | 14 Presentation viewer |
| 7 | Social posts with the public-release check | `#/jobs/<id>` → Social posts | 16 Social posts |
| 8 | Version compare (v1 against v2) | `#/jobs/<id>/compare` | 21 Version compare |
| 9 | Emergency alert | `#/emergency` | 22 Emergency alert |
| 10 | Review a kit with a line comment | `#/review/<id>` | 25 Review a kit |
| 11 | Signed, with the QR code | `#/review/<id>/signed` | 27 Signed successfully |
| 12 | Admin overview | `#/admin` | 30 Admin overview |
| 13 | AI models and measured speed | `#/admin/ai` | 34 AI models |
| 14 | Security & policies | `#/admin/security` | 36 Security and policies |
| 15 | Public page: genuine result (phone) | `http://localhost:8090/?r=PRM-…` | 45 Result genuine |
| 16 | Public page: fake message (phone) | `http://localhost:8090/#message` | 46 Result fake |

## Quick start (mock AI, no model)

The **mock AI** answers instantly by simple rules from the source (`backend/app/ai/mock_ai.py`), so every
screen, check, file and signature can be tried without the 18 GB model. You need Python 3.12 and Node LTS.

**1. Install.** With internet, from the project folder (`cd ~/Documents/"Pramaan AI"`):

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..
```

```bash
cd frontend && npm ci && cd ..
```

```bash
cp .env.example .env
```

Without internet, use the offline bundle instead (see [Offline installation](#offline-installation)).

**2. Choose the mock AI:** in `.env`, set `AI_MODE=mock` (and `MOCK_DELAY_SECONDS=2` to watch the
progress page work).

**3. Start:**

```bash
./scripts/start.sh
```

Open <http://localhost:5173>. The first time, **First-time setup** creates the first Admin (there are no
built-in accounts). As that Admin, add an Operator and a Reviewer on **Users & access** (each gets a
temporary password, shown once).

**4. Try it:** sign in as the Operator → **New transformation** → choose
`samples/sample-ransomware-report.txt` → **Next: safety check** → **Next** → tick outputs → **Generate**.
Click any sentence to see its source. **Send for review**; sign in as the Reviewer → **Review** →
**Approve & sign**. Start `./scripts/serve-verify.sh` and open the record's QR address to check it.
The [demo script](docs/DEMO_SCRIPT.md) walks through all of it in two minutes.

## Full start (local Sarvam 30B)

Needs the model (Sarvam 30B Q4_K_M GGUF, 6 files, about 18 GB) and llama.cpp's `llama-server`
(prebuilt, in `~/llama`). The offline installer puts both in place; on a computer with internet the model
can be fetched once with `~/llama/llama-server -hf sarvamai/sarvam-30b-gguf:Q4_K_M` (Ctrl+C when loaded).

1. In `.env`: `AI_MODE=local`.
2. Terminal 1 — the AI (port 8081). Wait for `server is listening` (about 2 minutes):

   ```bash
   ./scripts/start-ai.sh
   ```

3. Terminal 2 — the app:

   ```bash
   ./scripts/start.sh
   ```

4. On the dashboard, **Test AI** says namaste when the model answers.

**Speed:** on the 2017 Intel MacBook Pro (16 GB, no GPU) the model writes about 1–1.3 tokens a second, so
the sample report with an X thread and a LinkedIn post takes 25–35 minutes, most of it the fact sheet
(measured numbers in the [test report](docs/TEST_REPORT.md#performance-real-sarvam-30b) and
[docs/sarvam-runs/](docs/sarvam-runs/)). Jobs run in the background: leave the
page, and a notification says when it is done. On an office server with a GPU it is many times faster
([scaling](docs/ARCHITECTURE.md#scaling-to-an-office-server)).

| Part | Address |
|---|---|
| The app | http://localhost:5173 |
| Backend API, and its docs | http://localhost:8000, http://localhost:8000/docs |
| AI model (llama-server) | http://localhost:8081 |
| Public "Is this real?" page (`./scripts/serve-verify.sh`) | http://localhost:8090 |

## Offline installation

The target computer needs no internet. On a computer **with** internet, of the same kind (same operating
system and processor), make the bundle:

```bash
./scripts/make-offline-bundle.sh /Volumes/USB/pramaan-bundle
```

It holds the Python packages, the frontend packages, llama.cpp, the model (add `--no-model` for a
100 MB mock-only bundle), a manifest and a SHA-256 fingerprint of every file. Copy it and the project
folder to the offline computer (Python 3.12 and Node must be installed there from their own offline
installers), then:

```bash
./scripts/install.sh /Volumes/USB/pramaan-bundle
```

The installer checks the platform, Python, Node, memory (warns below 16 GB with the model), free disk
space and ports 8000 / 5173 / 8081 / 8090, verifies every file against the fingerprints, installs
everything, makes `.env` (with `AI_MODE=mock` if there is no model), and runs the backend tests.

## Roles

| Role | Colour | Does | Cannot |
|---|---|---|---|
| **Operator** | saffron | Adds sources, makes the safety choices and TLP label, generates, edits and regenerates outputs, compares versions, sends for review, emergency alerts, watch folder, downloads the kit | Approve; see users, settings or the audit trail |
| **Reviewer** | green | Reviews kits, comments on single sentences, approves and signs, sends back with reasons; signed records | Change a job; review a job they worked on |
| **Admin** | navy | Users and access requests, audit trail, AI models, templates and letterhead, security policies, record book (withdraw), public page update, backups | See job content |

Every role sees only its own menu, and the backend refuses other roles' requests (HTTP 403) on every
endpoint — `backend/tests/test_permissions.py` tries every endpoint with every role.

## Security

- **Offline by design:** no cloud service, CDN or external font; nothing leaves the computer. The cloud
  AI mode exists only for development and is never needed.
- **Before the AI:** private data and hidden instructions are found by rules (no AI); hidden values are
  replaced by placeholders, so the model never sees them; a leak check blocks any output that still
  contains one.
- **Sign-in:** argon2id password hashes, at least 12 characters; HttpOnly SameSite=Strict session cookie
  (8 hours, sign-out after inactivity, set by the Admin); lockout after wrong passwords; Origin check
  against cross-site requests; no default accounts.
- **At rest:** the database is encrypted with SQLCipher and every stored file with AES-256-GCM; the key is
  only in `.env` (`DB_KEY`), never in the database or backups.
- **Integrity:** append-only, hash-chained audit trail and record book (the database refuses changes, and
  "Verify chain" finds any edit); signed manifests with SHA-256 fingerprints of every file and text.
- **Public page:** holds only the public key and the records list (titles only for TLP:GREEN / CLEAR);
  checks run in the visitor's browser and nothing is uploaded.

Details: [ARCHITECTURE.md · Security model](docs/ARCHITECTURE.md#security-model).

## Limits (what is not done yet)

- **Indian languages:** outputs are written in English. Translation to the 22 scheduled languages
  (IndicTrans2), Indian voices (Indic Parler-TTS) and speech-to-text (IndicConformer) are designed
  (Stage 8 of the plan) but not built; the language choices are saved for when they are.
- **Inputs:** text, .txt, .pdf (with a text layer) and .docx. Scanned images, audio and video need OCR /
  speech-to-text (not built).
- **Video package:** script, storyboard and subtitles; no rendered MP4.
- **Speed:** the local 30B model is slow on a 16 GB laptop without a GPU (25–35 minutes for two short
  outputs, 39 minutes for three). One job runs at a time.
- **Signing:** the test key on this computer works end to end; signing with a Class 3 DSC USB token
  (PKCS#11) is designed but not tested with a real token.
- **Accounts:** no recovery codes; a forgotten Admin password needs another Admin, so make two Admins.
- **Updates:** installing signed update packages from USB is not built (copy the new version and run the
  installer; make a backup first).
- The mock AI is a rule-based stand-in for testing, not a language model.

## Troubleshooting

| Problem | What to do |
|---|---|
| **"Address already in use"** / `[Errno 48]` / "Port 5173 is already in use" | Another program uses the port. `./scripts/start.sh` stops an old Pramaan AI by itself; for anything else, find it and stop it: `lsof -nP -iTCP:8000 -sTCP:LISTEN` (or 5173, 8081, 8090), then `kill <PID>`. |
| `start-ai.sh` says port 8081 is in use | An earlier `llama-server` is still running. Use it, or stop it with Ctrl+C in its terminal (or `kill <PID>`). |
| **The AI is very slow** | Expected on a laptop: about 1–1.3 tokens/s; the fact sheet 11–24 minutes, then 3–7 minutes per short output. Generate fewer outputs (X thread and LinkedIn post first), use "Short" detail, close other apps (the model needs the memory), lower `MAX_TOKENS_...` in `.env`. The progress page shows tokens being written. Use `AI_MODE=mock` to demo instantly. |
| "Could not reach the AI" / jobs fail at once | `./scripts/start-ai.sh` is not running, or still loading (wait for `server is listening`). Then **Try again** on the job: finished parts are kept. |
| `start-ai.sh`: model not installed | Run `./scripts/install.sh` with a bundle that has the model, or download it once (see Full start). |
| The page says "The backend is not running" | Start `./scripts/start.sh` and watch its messages; a Python error there is the cause. |
| "cannot be opened with DB_KEY from .env" | The `.env` does not belong to this `data/` folder. Put back the right `.env` (keep a copy of it with every backup). |
| Locked out after wrong passwords | Wait 15 minutes, or ask an Admin to unlock or reset the password (**Users & access**). |
| A downloaded file is refused (private data found) | The leak check found a hidden value in that output: edit it out, or change the choice at the Safety check. |
| The phone cannot open the QR link | Set `VERIFY_BASE_URL` in `.env` to this computer's Wi-Fi address before signing, and run `./scripts/serve-verify.sh` (details in the [user guide](docs/USER_GUIDE.md)). |
| Tests fail after updating | Re-run the installer (or `pip install -r backend/requirements.txt` and `npm ci`). |

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

666 backend tests, always with the mock AI, a temporary data folder and test keys (your `data/` and
`.env` are never touched); they include the public page's own JavaScript, run with Node. Frontend type
check (no output means no errors):

```bash
cd frontend && npx tsc -b
```

The [test report](docs/TEST_REPORT.md) lists every feature, how it was tested, and the real Sarvam runs.

## AI provider switch

`AI_MODE` in `.env`: `local` (llama.cpp on this computer, the real deployment), `mock` (no model, for
tests and demos), `cloud` (Sarvam hosted API, development only; key in `SARVAM_API_KEY`, never in code).
All AI calls go through one module, `backend/app/ai/llm.py`; the rest of the app does not know which is in
use. Restart the app after changing `.env`.

## Folder map

```
backend/        FastAPI app: app/main.py, config.py (.env), db.py (SQLCipher), crypto.py, audit.py,
                notifications.py, watch.py, app_settings.py, branding.py, backup.py
  app/ai/         llm.py (the ONLY place that talks to the model), prompts/*.md, mock_ai.py
  app/pipeline/   ingest, factsheet, generate, checks, trace, segments, versions, compare, runner
  app/safety/     scanner, shield (hidden instructions), masking, tlp, decisions, public_check
  app/exporters/  docx, pdf, pptx, infographic (PNG), srt, text, kit (.zip)
  app/signing/    signer, sign_job, records (record book), messages ("Is this real?"), publish, qr
  app/auth/       passwords, accounts, sessions, deps (role checks)
  app/routes/     one file per area of the API
  tests/          666 tests
frontend/       React + TypeScript + Vite; design tokens in src/styles/tokens.css; fonts bundled
verify-page/    the public "Is this real?" page (static HTML + JS, works offline)
scripts/        start.sh, start-ai.sh, serve-verify.sh, install.sh, make-offline-bundle.sh
docs/           ARCHITECTURE, DEMO_SCRIPT, TEST_REPORT, USER_GUIDE
samples/        fictional test files (ransomware report, private data, hidden instruction)
Designs/        screen designs and the clickable prototype (reference)
models/, data/  the model and the app's data (never committed)
```

Fonts (Poppins, Hind, Rozha One, IBM Plex Mono, Noto Sans) are bundled under the SIL Open Font Licence.
Sarvam 30B is used under its model licence (Sarvam AI); llama.cpp under the MIT licence.
