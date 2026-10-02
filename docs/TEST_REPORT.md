# Pramaan AI · Test report

Tested on 1 October 2026 at version 1.0, and again on 2 October 2026 at **version 1.1** (Stage 8: Indian
languages and voice), on the development laptop (MacBook Pro 2017, Intel Core i7, 16 GB RAM, macOS 13.7,
Python 3.12.10, Node 22.14.0).

| | Result |
|---|---|
| Backend tests (v1.1) | **779 passed**, 0 failed (pytest, about 2 minutes), including 12 tests with the real language models |
| Every interface text has Hindi | **1,453 of 1,453** (`node scripts/i18n-keys.cjs --check`, run by `test_i18n.py`) |
| Public verify page (JavaScript) | **11 of 11 passed** (Node test runner, run by `test_verify_page.py`) |
| Frontend type check | **0 errors** (`npx tsc -b`) |
| Linter | **0 errors**, 12 style warnings (see Known limits) |
| Clean clone → offline install → start → demo (mock AI) | **Pass**, 3 small screen problems found and fixed (v1.0); v1.1 bundle with the language models installed and **779 tests passed** in the clean clone |
| Real Sarvam 30B, offline | **Works**: 3 outputs in 39 minutes, quality 93, every fact quote found in the source |
| Real language models, offline (v1.1) | **Work**: 7 outputs × 11 languages translated in 4.7 minutes with no changed values; Indian voices; Hindi and English speech-to-text |

## How it was tested

- **Automated backend tests** (`backend/tests/`, pytest): they always use the mock AI, a temporary data
  folder and test keys, so they never touch real data. They call the real API with real sign-ins, open the
  real exported files (Word, PDF, PowerPoint, PNG, zip), and run the public page's own JavaScript with Node.
  A parametrised **permission matrix** tries every endpoint with every role (and signed out).
- **Frontend:** TypeScript type check (`npx tsc -b`) and the project linter (oxlint).
- **In the browser** (Stages 9A and 9B): a click-through of every screen for every role, at full width and at
  720 px (= 200% zoom on a laptop), with an automated audit on each screen: text contrast (WCAG AA 4.5:1,
  3:1 for large text), form fields and buttons without names, page language, sideways scrolling; and the
  console checked for errors. Keyboard paths tried by hand: skip link, tabs with arrow keys, the search box,
  the menu drawer, dialogs.
- **Real AI:** runs of the sample report through Sarvam 30B on the development laptop (see Performance).
- **Language engines (Stage 8):** the automated tests use mock engines (instant, no models): a "translation"
  is the English with the language name in front, the voice is a tone, speech-to-text returns a fixed text.
  `tests/test_real_models.py` then tries every real engine on this computer (skipped where a model is not
  downloaded). The translated files in 11 scripts were opened and looked at by eye (letters joined
  correctly, Urdu right to left); the Hindi interface was read on every screen.
- **Installation:** a clean clone installed from the offline bundle, started, and the demo run in mock mode
  (see "Clean install check").

## Features and how each was tested

| Feature | How it was tested | Result |
|---|---|---|
| **Reading sources** (.txt with pages, PDF pages, Word with page breaks and tables, pasted text) | `test_ingest.py` (8); scanned PDFs and unknown types give clear messages | Pass |
| **Hidden text and characters removed** at ingest (white/tiny PDF text, hidden Word runs, zero-width characters) | `test_mock_and_source_checks.py`, `test_safety_api.py` (injection sample) | Pass |
| **Fact sheet** (chunking long sources, merging, quotes checked in the source, max 8 facts, entity types) | `test_factsheet.py` (11) | Pass |
| **Indicators by exact pattern** (CVE, IPs incl. defanged, hashes) | `test_factsheet.py`, `test_safety.py` | Pass |
| **The one LLM module** (JSON schema sent, streaming progress, server without schema support, retry once, truncated answers rescued, `<think>` removed) | `test_llm_json.py` (13), `test_system.py` (5), against a fake server | Pass |
| **Seven outputs from the fact sheet**, each citing fact ids | `test_jobs_api.py` (7), `test_mock_and_source_checks.py` (13) | Pass |
| **Source trace** (exact / close / missing quotes, highlight positions) | `test_trust.py` | Pass |
| **Unsupported sentences and values flagged** (numbers, dates, times, links not in the source; wrong year) | `test_trust.py` (22), `test_times.py` (13) | Pass |
| **Consistency across outputs** and **quality score** | `test_trust.py` | Pass |
| **Edit, regenerate, versions** (old versions kept, subtitles follow edited narration) | `test_trust.py` | Pass |
| **Safety scanner** (every detector, Aadhaar Verhoeff checksum, no false alarms on normal text, TLP suggestions) | `test_safety.py` (35) | Pass |
| **Masking** (placeholders before the AI; hidden values never reach the AI) | `test_safety.py`, `test_safety_api.py::test_hidden_values_never_reach_the_ai` | Pass |
| **Leak check** blocks downloads until edited out | `test_safety_api.py`, `test_safety.py` | Pass |
| **Prompt-injection shield** (phrases found, removed by default, logged if kept) | `test_safety.py`, `test_mock_and_source_checks.py` | Pass |
| **TLP rules** (RED/AMBER switch public outputs off) | `test_safety.py`, `test_safety_api.py` | Pass |
| **Real files** (Word, PDF, PowerPoint with notes, PNG in 3 layouts, .srt, .txt, campaign kit .zip, encrypted copies) | `test_exports.py` (14): every file is opened with its own library | Pass |
| **Long titles fit in footers**; mock captions read as phrases | `test_alerts_kit_polish.py`, `test_trust.py` | Pass |
| **Accounts** (argon2id, password rules, first-time setup once, lockout, access and reset requests, last Admin kept) | `test_accounts.py` (14) | Pass |
| **Sign-in by username, employee ID or email**; profile changes only language and preferences | `test_profile_accounts.py` (7) | Pass |
| **Sessions** (HttpOnly SameSite cookie, fingerprint stored, 8 h and inactivity limits, Origin check) | `test_sessions.py` (12) | Pass |
| **Roles on every endpoint** | `test_permissions.py`: the matrix (every endpoint × 4) and a test that fails if a new endpoint is not in it | Pass |
| **Review** (submit, send back, resubmit as v2, approve; separation of duties) | `test_review.py` (8) | Pass |
| **Line comments and send-back reasons**; reviewer dashboard numbers | `test_review_comments.py` (4) | Pass |
| **Signing** (signature verifies, one changed byte fails, QR files, read-only encrypted signed files, TLP:RED publishes no title, new versions) | `test_signing.py` (11) | Pass |
| **Record book** (withdraw as a new entry, database refuses changes, verify finds changed, re-hashed or deleted entries and changed files) | `test_record_book.py` (9) | Pass |
| **"Is this real?" message checker** (exact, forwarded, changed with the changed words, unknown, scam signs, withdrawn) | `test_messages.py` (11) | Pass |
| **Public verify page** (signatures with and without Web Crypto, file check, tampering, same answers as Python) | `test_verify_page.py` (5) runs `verify-page/tests/verify.test.mjs` with Node | Pass |
| **Audit trail** (everything logged, no passwords, chain verify finds changes and deletions) | `test_audit.py` (8), `test_no_secrets_in_logs.py` (3) | Pass |
| **Encryption at rest** (database unreadable without the key, AES-GCM files, tampered files refused, migration of plain data) | `test_encryption.py` (10) | Pass |
| **Notifications, search, dashboard, job filters** | `test_notifications_search.py` (5) | Pass |
| **Watch folder** (drafts wait at the Safety check and never start by themselves; folders outside `data/watch/` refused; duplicates; files still copying) | `test_watch.py` (7) | Pass |
| **Version compare** (word diff, "five" → "six", v1 against v2 after a send-back) | `test_compare.py` (3) | Pass |
| **Emergency alert** (public-release check, SMS length, fast-track review, on-duty reviewers) | `test_alerts_kit_polish.py`, `test_profile_accounts.py` | Pass |
| **Admin: overview, AI speed from real runs, speed test** | `test_admin_system.py` | Pass |
| **Security policy really applies** (scanner switches, extra classification words, inactivity sign-out, lockout) | `test_admin_system.py` | Pass |
| **Letterhead** (office name and logo inside real PDF, Word, PowerPoint, PNG, text files; "Issued by"; logo checks) | `test_admin_files.py` | Pass |
| **Backups** (encrypted database copy that opens with the key; only listed backups downloadable) | `test_admin_files.py` | Pass |
| **All screens for every role**, menus per role, "You don't have access" | Browser click-through (Stages 9A, 9B) and the demo on a clean install | Pass: no console errors |
| **Accessibility** (contrast, names, skip link, focus, 200% zoom, not colour alone) | Browser audit on every screen at 1024 px and 720 px | Pass after fixes (stepper and badge contrast, sideways scrolling of two tables) |
| **Offline installation** | Clean clone + `install.sh` from a bundle (see below) | Pass: 155 files checked, 666 tests passed, no internet used (v1.0); v1.1 with language models: 1,660 files checked, 779 tests passed |
| **Pluggable language engines** (`TRANSLATE_ENGINE`, `TTS_ENGINE`, `STT_ENGINE`, each with a mock; unknown names refused; status on Admin → AI models) | `test_lang_engines.py` (16) | Pass |
| **Outputs in Indian languages** (picker, 22 languages, translated from the English, fact ids kept, values checked again, "Changed in translation", native-speaker tick needed before approval, translations follow English edits, add a language later) | `test_translations.py` (13) | Pass |
| **IndicTrans2 details** (placeholders and values kept, script conversion, Hindi visarga used as a colon, dropped hashtags put back) | `test_lang_engines.py`, `test_real_models.py` | Pass |
| **Files in every Indian script** (PDF, Word, PowerPoint, PNG for 12 scripts; shaping; right to left; fixed labels translated; dates) | `test_indian_scripts.py` (29) | Pass, and checked by eye |
| **Voice** (narration MP3, MP4 video with captions and subtitles, silent video where no voice exists, "Read results aloud", recordings as sources, bad recordings refused) | `test_voice.py` (5) | Pass |
| **Emergency alert in every language** (SMS as an output, 160 / 70 characters, 1930 kept, preview cards, voice announcement, tick all translations) | `test_alert_languages.py` (4) | Pass |
| **The app in English and Hindi** (every text has Hindi; the choice saved per user) | `test_i18n.py` (2), browser check of every screen in Hindi | Pass |
| **Shorter / More formal / Simpler** (new version, facts and numbers kept, checks run again, translations follow; translations and unknown changes refused) | `test_rewrite_mentions.py` (3) | Pass (mock AI; not yet tried with the real Sarvam model) |
| **@mentions and the Mentions tab** | `test_rewrite_mentions.py` (1) | Pass |
| **Real language models** (IndicTrans2 hi/ta/ur keep every number, each Piper and macOS voice, Whisper hears English, IndicConformer hears Hindi, Tamil model runs) | `test_real_models.py` (12) | Pass (30 s) |
| **Real Sarvam 30B, offline** | Recorded runs (see Performance) | Pass (slow: about 1 token/s on this laptop) |

## Test runs

Commands (from the project folder):

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx tsc -b && npm run lint
```

| Test file | Tests | | Test file | Tests |
|---|---|---|---|---|
| `test_accounts.py` | 14 | | `test_permissions.py` | 4 (+ matrix of every endpoint × role) |
| `test_admin_files.py` | 4 | | `test_profile_accounts.py` | 7 |
| `test_admin_system.py` | 4 | | `test_record_book.py` | 9 |
| `test_alerts_kit_polish.py` | 7 | | `test_review.py` | 8 |
| `test_audit.py` | 8 | | `test_review_comments.py` | 4 |
| `test_compare.py` | 3 | | `test_safety.py` | 35 |
| `test_encryption.py` | 10 | | `test_safety_api.py` | 8 |
| `test_exports.py` | 14 | | `test_sessions.py` | 12 |
| `test_factsheet.py` | 11 | | `test_signing.py` | 11 |
| `test_ingest.py` | 8 | | `test_system.py` | 5 |
| `test_jobs_api.py` | 7 | | `test_times.py` | 13 |
| `test_llm_json.py` | 13 | | `test_trust.py` | 22 |
| `test_messages.py` | 11 | | `test_verify_page.py` | 5 (runs 11 JavaScript tests) |
| `test_mock_and_source_checks.py` | 13 | | `test_watch.py` | 7 |
| `test_no_secrets_in_logs.py` | 3 | | `test_notifications_search.py` | 5 |
| `test_lang_engines.py` (v1.1) | 14 | | `test_translations.py` (v1.1) | 10 |
| `test_indian_scripts.py` (v1.1) | 8 | | `test_voice.py` (v1.1) | 5 |
| `test_alert_languages.py` (v1.1) | 4 | | `test_i18n.py` (v1.1) | 2 |
| `test_real_models.py` (v1.1) | 8 | | `test_rewrite_mentions.py` (v1.1) | 4 |

The table counts test functions; with parametrised cases (the permission matrix, the safety detectors, the
scripts and voices) pytest runs **779** tests. The run on 2 October 2026: `779 passed, 1 warning in 112.90s`
(v1.0 on 1 October: `666 passed`). The warning is a deprecation notice inside the FastAPI test client, not
from our code.

## Performance (real Sarvam 30B)

All runs: Sarvam 30B, Q4_K_M GGUF (18 GB, 6 files), llama.cpp `llama-server` build 11263 on CPU, started by
`./scripts/start-ai.sh` (`-c 4096 -t 4 -np 1 -b 512 --reasoning-budget 0`), no internet. Source: the sample
ransomware report (3,883 characters, 1 page). Timings come from `llama-server`'s own log and from the job.

**Run of 1 October 2026** (recorded for the demo, [full record with the texts](sarvam-runs/run-2026-10-01-2041.md)):

| Step | Minutes | Prompt read | Tokens written | Writing speed | Quality |
|---|---|---|---|---|---|
| Fact sheet (8 facts) | 24.0 | 1,295 tokens at 4.7/s | 1,111 | 0.95 tokens/s | 8 of 8 quotes found |
| X thread | 5.7 | 870 tokens at 5.5/s | 191 | 1.05 tokens/s | 87 |
| LinkedIn post | 3.5 | 112 new tokens (rest cached) | 171 | 0.98 tokens/s | 93 |
| Executive summary | 5.7 | 170 new tokens (rest cached) | 338 | 1.12 tokens/s | 100 |
| **Whole job** | **39.2** | | **1,811** | **about 1 token/s** | **93** |

**Runs during Stage 3 (30 September 2026)**, same laptop with fewer apps open: fact sheet about 11 minutes,
X thread about 7, LinkedIn post about 5 (about 23 minutes for the job); writing speed 1.3–1.4 tokens/s; a
1,300-token prompt took up to 6 minutes to read before the first token.

What the numbers mean:

- **Minutes per output:** 3.5–7 minutes for a short output once the fact sheet exists; the fact sheet is
  the slow part (11–24 minutes) and is written once per job.
- **Speed depends on free memory.** The 18 GB model does not fit in 16 GB of RAM, so macOS reads parts of
  it from disk while it writes. On 1 October the Pramaan app, the Claude desktop app and a browser were open
  and about 9 GB of swap was used: about 1.0 token/s against 1.3–1.4 with fewer apps open.
- **Prompt caching works:** after the first output, the next ones read only their own 100–200 new tokens,
  because the fact sheet part of the prompt is reused.
- **Quality:** all 3 outputs passed the checks (numbers agree across outputs, no values that are not in the
  source); the X thread scored 87 because some of its words are not tied to a single fact.
- Expected on an office server with a GPU: many times faster (see
  [ARCHITECTURE.md](ARCHITECTURE.md#scaling-to-an-office-server)); not measured here.

## Performance (language models, v1.1)

Measured on 2 October 2026 on the same laptop, CPU only, 8-bit models:

| Step | Time |
|---|---|
| IndicTrans2: load the model | 1.1 s |
| IndicTrans2: 4 sentences (66 words) into Hindi / Tamil / Bengali / Urdu | 1.6 / 1.7 / 1.4 / 1.6 s |
| IndicTrans2: the showcase job, 7 outputs × 11 languages (77 translations) | 4.7 minutes, 0 changed values |
| Piper voice (Hindi, Priyamvada): 48 s of speech | 16.4 s |
| macOS voice (Rishi, Indian English): 36 s of speech | 1.4 s |
| MP3 from the speech (ffmpeg) | 0.3 s |
| IndicConformer Hindi: 48 s of speech to text | 6.0 s the first time (loading), 4.4 s after |
| Whisper small (English): 36 s of speech to text | 9.8 s the first time, 7.3 s after |
| MP4 video of the showcase job's Hindi video package (Hindi voice, captions, subtitles; H.264 + AAC) | 12.1 s |

Translation is fast because IndicTrans2 is a small, specialised model (200 million parameters) next to the
30-billion-parameter Sarvam model; translating through Sarvam (`TRANSLATE_ENGINE=llm`) works but would take
minutes per output on this laptop.

## Clean install check

1 October 2026, from version `91e83a6`:

1. **Bundle** made with `./scripts/make-offline-bundle.sh <folder> --no-model` on the connected laptop: 102 MB,
   40 Python wheels, npm cache, llama.cpp, `MANIFEST.txt`, `SHA256SUMS` (155 files). (The model files are
   added the same way without `--no-model`; they come from the Hugging Face cache, 18 GB.)
2. **Clean clone** with `git clone` into a new folder whose path has spaces (`…/clean check/Pramaan AI`).
3. **Install:** `./scripts/install.sh <bundle> --no-model`, with pip and npm pointed at an address that does
   not exist, so any download attempt would fail. Result in 2.5 minutes: platform, Python, Node, memory,
   disk checked; ports 8000 and 5173 reported in use (by the main copy); 155 fingerprints matched; 41 Python
   packages and the frontend packages installed offline; llama.cpp already present and kept; `.env` made with
   `AI_MODE=mock`; **666 tests passed**. `git status` afterwards: nothing new outside git-ignored folders.
4. **Start:** `./scripts/start.sh` refused, correctly, because another copy was using ports 8000/5173
   (it never stops a program that is not its own). The same servers were then started on spare ports
   (backend 8002, frontend 5175 with `API_TARGET`), and `./scripts/serve-verify.sh` on 8090. The secret keys
   were made on first start and saved in `.env`.
5. **Demo in mock mode** (every step of [DEMO_SCRIPT.md](DEMO_SCRIPT.md), in the browser): first-time setup
   (Admin) → Priya uploads `sample-private-data.txt` + `sample-injection.txt` → 15 findings (13 kinds), the
   hidden instruction and 8 hidden characters removed, TLP:AMBER suggested, public outputs switched off →
   advisory + executive summary ready at once → source trace highlights the quote → submit for review → Arjun
   adds a line comment → **Approve & sign** (4 files, record PRM-2026-000001, chain intact) → verify page
   shows **Genuine** (AMBER: only number, date and fingerprints published) → the fake alert gives **Not
   genuine** with 4 reasons and "call 1930". The showcase job (all 7 outputs) was ready with quality 98 and
   the one yellow "not linked" sentence in the LinkedIn post; every download of every output worked.
   No errors in the console.

**Fixed during the check:**

| Found | Fix |
|---|---|
| Memory and disk on the Admin overview shown as "16384.0 MB", "139231.5 MB" | Sizes over 1 GB are shown in GB ("16 GB", "136 GB") |
| In a window under 1,100 px (or at 200% zoom) the source trace sheet did not close with Escape | Escape closes it, like the other dialogs |
| …and on the review page it covered the comment box, so a Reviewer could not comment there | The sheet takes at most half the screen and the comment box scrolls into the top half |
| Demo script button names ("Send for review", "Sign") did not match the screens | Corrected ("Submit for review", "Sign 4 files", "Open results") |

## Known limits found while testing

- The local 30B model is slow on a 16 GB laptop: the model (18 GB) does not fit in memory, so its weights
  are read from disk while it writes. Speed depends on what else is open (see Performance). Use the mock AI
  for live demos and a recorded run for the real model.
- Not built yet: OCR for scanned files, signing with a real DSC USB token (designed, not tested), update
  packages from USB, voices for languages other than Hindi, Telugu, Malayalam, Urdu and English,
  speech-to-text for languages other than Hindi, Tamil and English.
- Machine translations need a native speaker: only the Hindi labels and menus were read by a person. The
  smaller languages are weaker (IndicTrans2's own published scores).
- The rewrite buttons and the `llm` translation engine were tested with the mock AI only, not yet with the
  real Sarvam model.
- The linter reports 12 style warnings (no errors): fast-refresh hints and setState-in-effect patterns;
  they do not affect behaviour.
- `scripts/start.sh` always uses ports 8000 and 5173, so two copies cannot run with it at the same time
  (the second one stops with a clear message). A second copy can be started by hand on other ports, as in
  the clean install check.
