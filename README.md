# Pramaan AI (प्रमाण) — Content you can prove.

**One report in, every format out, and every line traceable to its source.** Pramaan AI turns one
source — a threat report, an advisory, a policy note — into an advisory, an executive summary, a slide
deck, a video package, an infographic, a LinkedIn post and an X thread — in English and the **22 scheduled
Indian languages**, with Indian voices. It runs **entirely offline on the organisation's own computer**
with Indian AI models (Sarvam 30B, AI4Bharat IndicTrans2 and IndicConformer). Every sentence it writes is
linked to the place in the source it came from; a Reviewer approves and digitally signs the result; and
anyone can check a document or a forwarded message on a public **"Is this real?"** page.

Smart India Hackathon 2026 · Problem Statement **26154** (NTRO) · Gen AI Platform for Automated Content
Transformation.

| Read next | |
|---|---|
| [DOWNLOAD.md](DOWNLOAD.md) | **Download Installers**: Official downloads for macOS, Windows, & Linux |
| [USER_GUIDE.md](USER_GUIDE.md) | **User Guide**: Step-by-step instructions for all features & offline setup |
| [DEPLOYMENT.md](DEPLOYMENT.md) | **Deployment Guide**: Architecture, packaging, security & release procedure |
| [DEVELOPER_BUILD.md](DEVELOPER_BUILD.md) | **Developer Build Guide**: Building installers from source code |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **Troubleshooting Guide**: Solutions for common runtime errors |

---

# 📥 Download Pramaan AI

Download official cross-platform installers from the [**GitHub Releases**](https://github.com/sanchaymurugan22-prog/Pramaan-AI/releases/latest) page:

- 🍎 **macOS (Intel & Apple Silicon)**: [`Pramaan AI-1.0.0.dmg`](https://github.com/sanchaymurugan22-prog/Pramaan-AI/releases/latest)
- 🪟 **Windows (10 / 11)**: [`Pramaan AI Setup 1.0.0.exe`](https://github.com/sanchaymurugan22-prog/Pramaan-AI/releases/latest)
- 🐧 **Linux (Ubuntu / Fedora / Debian)**: [`Pramaan AI-1.0.0.AppImage`](https://github.com/sanchaymurugan22-prog/Pramaan-AI/releases/latest) or `pramaan-ai-desktop_1.0.0_amd64.deb`

> **Note for Users**: Pramaan AI is a self-contained desktop application. You do **NOT** need Python, Node.js, npm, Git, or Terminal commands to install or use Pramaan AI. Simply download the installer for your OS, run it, and complete the First-Run Setup Wizard!

---

## Features

**Writing**
- **One fact sheet, seven outputs.** The AI reads the source once into a fact sheet (facts, each with
  its quote and page; dates; recommended actions; CVEs, IPs and file hashes found by exact patterns).
  Every output is written from that fact sheet, so all outputs agree.
- **Seven outputs as real files:** CERT-In style advisory (PDF, Word), executive summary (PDF, Word),
  presentation with speaker notes (PowerPoint), video package (script and storyboard in Word, subtitles
  as .srt), infographic (PNG), LinkedIn post and X thread (text). All together as one campaign kit (.zip).
- Settings per job: audience, tone, objective, style, level of detail. **Shorter / More formal / Simpler**
  buttons rewrite one output with that one change (facts, numbers and fact ids kept; every check runs again).
- **Emergency alert:** a short public alert with a live public-release check (no panic wording, no
  private data, SMS length), in every chosen language with a voice announcement (.mp3), sent straight to
  the on-duty Reviewers for fast-track approval.
- **Watch folder:** reports dropped in a folder become drafts that wait for a person at the Safety check.

**Languages and voice** (Stage 8)
- **Outputs in 22 Indian languages** (pick any of them; English is always made): each is translated from
  the English output by **IndicTrans2** on this computer (or by the AI model, `TRANSLATE_ENGINE=llm`).
  Fact ids stay, so the source trace still works; every number, date, IP, CVE, hash, link and hashtag is
  checked again and marked red if the translation changed it. Each translation says **"Machine translated
  - needs a native-speaker check"** until a Reviewer ticks it; approval waits for that.
- **Files in every Indian script:** PDF, Word, PowerPoint and PNG with Noto Sans fonts, correct joining
  of letters (HarfBuzz shaping) and right-to-left Urdu, Kashmiri and Sindhi.
- **Voice:** the video package as narration (.mp3) and as a **video (.mp4)** made from the storyboard
  with subtitles; "Read results aloud". Voices: Piper (Hindi, Telugu, Malayalam, Urdu) and macOS (Hindi,
  Indian English); other languages show "audio not available".
- **Recordings as sources:** an audio or video file becomes text by speech-to-text (IndicConformer for
  Hindi and Tamil, Whisper small for English), then goes through the same Safety check.
- **The app in English or Hindi** (switch at the top right, remembered for each user).

**Trust**
- **Source trace:** click any sentence to see the fact it uses and the quote highlighted in the source.
- Sentences not linked to a fact are marked in yellow; numbers, dates or names not in the source in red.
- Reviewers comment on single sentences and can name a person with `@` (they see it on the **Mentions** tab).
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
| 17 | Results in Hindi, language switch, "Machine translated" note | `#/jobs/<id>` → हिन्दी | 13 Results (Stage 8) |
| 18 | Emergency alert preview cards in many languages | `#/emergency` | 22 Emergency alert (Stage 8) |
| 19 | The app in Hindi (switch at the top right) | `#/` | 08 Operator dashboard |

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

**Languages and voice (optional).** Either download the models once (about 2.6 GB download, 0.9 GB
kept; IndicTrans2 asks you to click "Agree" on its Hugging Face page and to put `HF_TOKEN` in `.env`):

```bash
backend/.venv/bin/python scripts/download-models.py
```

or try everything with test engines: in `.env` set `TRANSLATE_ENGINE=mock`, `TTS_ENGINE=mock` and
`STT_ENGINE=mock` (a "translation" is the English with the language name in front; the voice is a tone).

**3. Start:**

```bash
./scripts/start.sh
```

Open <http://localhost:5173>. The first time, **First-time setup** creates the first Admin (there are no
built-in accounts). It asks for the **setup code** that the backend prints in the terminal where you ran
`start.sh` (a box saying "Setup code: XXXX-XXXX"), so only the person who installed Pramaan AI can become
its first Admin. The code works once; after 5 wrong tries or a restart a new one is printed. As that Admin, add an Operator and a Reviewer on **Users & access** (each gets a
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

It holds the Python packages, the frontend packages, llama.cpp, the model (add `--no-model` to leave
out the 18 GB model), the language and voice models (0.9 GB; `--no-lang-models` to leave them out), a
manifest and a SHA-256 fingerprint of every file. Copy it and the project
folder to the offline computer (Python 3.12 and Node must be installed there from their own offline
installers), then:

```bash
./scripts/install.sh /Volumes/USB/pramaan-bundle
```

The installer checks the platform, Python, Node, memory (warns below 16 GB with the model), free disk
space and ports 8000 / 5173 / 8081 / 8090, verifies every file against the fingerprints, installs
everything, makes `.env` (with `AI_MODE=mock` if there is no model; translation through the AI model and
macOS voices if there are no language models), and runs the backend tests.

## Roles

| Role | Colour | Does | Cannot |
|---|---|---|---|
| **Operator** | saffron | Adds sources (documents and recordings), makes the safety choices and TLP label, chooses languages, generates, edits, rewrites and regenerates outputs, compares versions, sends for review, emergency alerts, watch folder, downloads the kit | Approve; tick the native-speaker check; see users, settings or the audit trail |
| **Reviewer** | green | Reviews kits, comments on single sentences (with `@` mentions), ticks the native-speaker check of translations, approves and signs, sends back with reasons; signed records | Change a job; review a job they worked on |
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

- **Indian languages:** outputs are written in English first and then machine translated; a native speaker
  must check each translation (the app asks for it). IndicTrans2's own published scores are lower for the
  smaller languages (for example Santali, Manipuri, Kashmiri, Sindhi) than for Hindi, Tamil or Bengali.
- **Voices** exist for Hindi, Telugu, Malayalam, Urdu and Indian English only; **speech-to-text** for
  Hindi, Tamil and English only. Other languages say "audio not available".
- **The interface** is in English and Hindi only (Hindi texts: menus and buttons chosen by hand, not yet checked by a native speaker;
  the rest machine translated).
- **Inputs:** text, .txt, .pdf (with a text layer), .docx and recordings. Scanned images need OCR (not built).
- **Video:** the MP4 is the storyboard as still pictures with captions and narration, not animation.
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

779 backend tests, always with the mock AI and mock language engines, a temporary data folder and test
keys (your `data/` and `.env` are never touched); they include the public page's own JavaScript and the
check that every interface text has Hindi, run with Node. `tests/test_real_models.py` also tries each real
language engine (IndicTrans2, every voice, IndicConformer, Whisper) when its model is downloaded, about 30
seconds; `SKIP_REAL_MODELS=1` skips them. Frontend type check (no output means no errors):

```bash
cd frontend && npx tsc -b
```

The [test report](docs/TEST_REPORT.md) lists every feature, how it was tested, and the real Sarvam runs.

## AI provider switch

`AI_MODE` in `.env`: `local` (llama.cpp on this computer, the real deployment), `mock` (no model, for
tests and demos), `cloud` (Sarvam hosted API, development only; key in `SARVAM_API_KEY`, never in code).
All AI calls go through one module, `backend/app/ai/llm.py`; the rest of the app does not know which is in
use. Restart the app after changing `.env`.

The language engines switch the same way (each has a `mock` for tests):

| Setting | Choices |
|---|---|
| `TRANSLATE_ENGINE` | `indictrans2` (on this computer, default) · `llm` (through `llm.py`, slow) · `mock` |
| `TTS_ENGINE` | `piper` (Piper voices, then macOS voices) · `say` (macOS voices only) · `mock` |
| `STT_ENGINE` | `onnx` (IndicConformer, Whisper) · `mock` |

## Folder map

```
backend/        FastAPI app: app/main.py, config.py (.env), db.py (SQLCipher), crypto.py, audit.py,
                notifications.py, watch.py, app_settings.py, branding.py, backup.py
  app/ai/         llm.py (the ONLY place that talks to the model), prompts/*.md, mock_ai.py
  app/pipeline/   ingest, factsheet, generate, checks, trace, segments, versions, compare, runner
  app/safety/     scanner, shield (hidden instructions), masking, tlp, decisions, public_check
  app/exporters/  docx, pdf, pptx, infographic (PNG), srt, text, video (MP3/MP4), shaped (Indian scripts), kit (.zip)
  app/lang/       languages, translate (+ indictrans), tts, stt, audio, labels (Stage 8)
  app/signing/    signer, sign_job, records (record book), messages ("Is this real?"), publish, qr
  app/auth/       passwords, accounts, sessions, deps (role checks)
  app/routes/     one file per area of the API
  tests/          779 tests
frontend/       React + TypeScript + Vite; design tokens in src/styles/tokens.css; fonts bundled;
                src/i18n/ (English and Hindi texts)
verify-page/    the public "Is this real?" page (static HTML + JS, works offline)
scripts/        start.sh, start-ai.sh, serve-verify.sh, install.sh, make-offline-bundle.sh,
                download-models.py (+ the converters it uses), make-labels.py, make-ui-hindi.py
docs/           ARCHITECTURE, DEMO_SCRIPT, TEST_REPORT, USER_GUIDE
samples/        fictional test files (ransomware report, private data, hidden instruction)
Designs/        screen designs and the clickable prototype (reference)
models/, data/  the models and the app's data (never committed)
```

## Licences of the models, voices and fonts

| Part | Licence |
|---|---|
| Sarvam 30B (GGUF) | Sarvam AI model licence |
| llama.cpp | MIT |
| AI4Bharat IndicTrans2 en→indic distilled 200M | MIT (converted here to CTranslate2 8-bit) |
| AI4Bharat IndicConformer Hindi, Tamil (ONNX by OpenVoiceOS) | MIT |
| Whisper small (ONNX by onnx-community) | MIT (OpenAI) |
| Piper voice Hindi "Priyamvada" | **CC BY-NC-SA 4.0: non-commercial only** |
| Piper voice Telugu "Padmavathi" | CC BY 4.0 (data: AI4Bharat IndicVoices-R): give credit |
| Piper voice Malayalam "Meera" | trained on the IIT Madras Indic TTS corpus: that corpus's own licence (check before any commercial use) |
| Piper voice Urdu "Fasih" | MIT |
| macOS voices Lekha (Hindi), Rishi (Indian English) | Apple macOS licence: for use on that Mac; check before publishing recordings |
| sherpa-onnx, onnxruntime, CTranslate2, onnx-asr | Apache 2.0, MIT, MIT, MIT |
| espeak-ng (inside sherpa-onnx, turns text into sounds for Piper) | GPL-3.0 |
| ffmpeg (inside imageio-ffmpeg, makes MP3 and MP4) | GPL (this build includes x264) |
| HarfBuzz (uharfbuzz), FreeType (freetype-py) | MIT, FreeType licence |
| Fonts: Poppins, Hind, Rozha One, IBM Plex Mono, Noto Sans and Noto Naskh Arabic | SIL Open Font Licence 1.1 |

The voice licences matter for a real deployment: before using the Hindi voice for public announcements,
get a voice with a licence that allows it (or use `TTS_ENGINE=say` within Apple's terms), and credit
AI4Bharat for the Telugu voice.
