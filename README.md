# Pramaan AI (प्रमाण) — Content you can prove.

Offline, Indian-AI platform that turns one source into advisories, summaries, slides, video
packages, infographics and social posts in Indian languages, with every line traced to its source
and every document signed and verifiable.

Smart India Hackathon · Problem Statement 26154 · NTRO.

**Current stage: 7 — Anti-fake.** When a Reviewer approves a job it is **signed**: every final file
gets a QR code and a record number (`PRM-2026-000123`), its SHA-256 fingerprint and the fingerprint of
every output's text go into a signed manifest, and the job gets an entry in a hash-chained **record
book** (an Admin can withdraw a record; nothing is ever deleted). A static public **"Is this real?"**
page (`verify-page/`, no backend, works offline) checks a record from its QR code, a dropped file,
or a pasted WhatsApp / SMS message, in English and Hindi. See "Signing and verification (Stage 7)".

Stage 6B — Accounts and data protection: people sign in. There are three roles,
checked by the backend on every request: **Operator** (makes and changes jobs, submits them for
review), **Reviewer** (approves or sends back with notes, never their own job) and **Admin** (users,
access requests, audit trail). Every action goes into a hash-chained audit trail, and the database
and every stored file are encrypted. See "Accounts and roles (Stage 6B)" and "Encryption at rest
(Stage 6B)" below.

Stage 6A — Safety: a new transformation has 3 steps: *Add sources → Safety
check → Outputs & settings*. Before any AI reads a source, a rule-based scanner (no AI, offline)
finds private data (Aadhaar, PAN, phones, emails, bank details, passports, vehicles, GPS, internal
IPs and host names, passwords and keys, classification markings), attack indicators, and text that
tries to control the AI. The operator decides what to hide and picks a TLP sharing label; hidden
values are swapped for placeholders before the AI, and a leak check blocks any output that still
contains one. See "Safety (Stage 6A)" below.

Earlier stages: paste text or upload a .txt / .pdf / .docx, and the app builds
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
ReportLab and Pillow; Stage 6B adds argon2-cffi, cryptography and sqlcipher3, all with ready-made
builds for Intel Macs; Stage 7 adds qrcode. New tables and columns are added to your existing database automatically
when the backend starts; nothing is deleted. On the first Stage 6B start the database and files are
encrypted — see "Encryption at rest" — and `APP_SECRET_KEY` and `DB_KEY` are made and saved in `.env`.)

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

The very first time, the app shows **First-time setup**: create the first Admin account there (there
are no built-in or default accounts). Everyone else gets an account from that Admin.

If an old Pramaan AI is still running on port 8000 or 5173 (for example a terminal closed without
Ctrl+C), `start.sh` stops it first and says so. If another program uses one of those ports, it
tells you which one and does not start.

| Part | Address |
|---|---|
| Frontend (the app) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (auto-generated) | http://localhost:8000/docs |
| AI model (llama-server) | http://localhost:8081 |
| Public "Is this real?" page (Stage 7, `./scripts/serve-verify.sh`) | http://localhost:8090 |

## Try it quickly with the mock AI (no model needed)

The mock AI answers instantly, with no model: it builds its answers from the source you give it,
by simple rules (`backend/app/ai/mock_ai.py`). Like the real AI, it only sees the MASKED text
(`[PHONE-1]` …) and never the instructions you removed, so masking, the leak check and every trust
check can be tested with it. Facts: up to 8 informative sentences of the source (with numbers,
dates, names or placeholders), each quoting its own sentence; dates by pattern; actions from a
"Recommended actions" list (or sentences starting with a verb like "Please", "Apply"); severity
from keywords. Outputs: simple templates filled with those facts. One LinkedIn paragraph cites no
fact on purpose, so the yellow "Not linked to a fact" warning can be seen.

1. In `.env`, set `AI_MODE=mock` (optionally `MOCK_DELAY_SECONDS=3` to see the progress display).
2. Start the app: `./scripts/start.sh` (no need for `start-ai.sh`).
3. Open <http://localhost:5173> and sign in as an **Operator** (see "Accounts and roles"), click
   **New transformation**.
4. Click **Choose files** and pick `samples/sample-ransomware-report.txt` (or paste its text),
   then **Next: safety check**.
5. The Safety check shows what was found (for this report: only attack indicators) and suggests
   TLP:GREEN. Click **Next: outputs and settings**.
6. Tick some outputs, click **Generate**. The Results page shows the fact sheet, then each output.
7. Click any sentence: the **Source trace** panel on the right shows the fact it uses and the quote
   highlighted in the source. (See "Trust" below for everything else to try.)
8. Under each output, click a **Download** button; at the top, **Download campaign kit (.zip)**.

Set `AI_MODE=local` again (and restart `start.sh`) to use the real model.

## Try it with the real local AI

The real model is slow on the dev laptop (about 1.4 tokens a second), so start small:

1. `.env`: `AI_MODE=local`. Terminal 1: `./scripts/start-ai.sh`. Terminal 2: `./scripts/start.sh`.
2. **New transformation** → choose `samples/sample-ransomware-report.txt` → **Next: safety check**
   → **Next** → tick only **X thread** and **LinkedIn post** (the default) → **Generate**.
3. Measured on the dev laptop with the sample report: fact sheet about 11 minutes (the model first
   reads the whole report, then writes the facts), X thread about 7 minutes, LinkedIn post about
   5 minutes — roughly 25 minutes in total. The page shows what is happening
   and how many tokens have been written. You can leave the page and come back via **My jobs**.

If something fails (for example llama-server was not running), start the model and click
**Try again** on the Results page: finished parts are kept, only the rest is redone.

## How it works

```
source (text / .txt / .pdf / .docx)
  → ingest        plain text per page, saved under data/jobs/<id>/sources/; hidden characters
                  and hidden Word/PDF text removed (Stage 6A)
  → safety scan   (no AI) private data, indicators, suspicious instructions → the operator's
                  choices + TLP label; hidden values become placeholders like [PHONE-1]
  → fact sheet    ONE model call per chunk (long sources are split to fit the 4096-token context),
                  merged; each fact has a quote that is checked against the source;
                  IPs, CVEs and file hashes are found by exact patterns, not by the model
  → outputs       each written FROM THE FACT SHEET with its own prompt (backend/app/ai/prompts/)
                  and JSON shape; short outputs first; every part lists the fact ids it uses
  → checks        (no AI) every sentence linked to a fact; values not in the source flagged;
                  the same numbers in every output; a 0-100 quality score (Stage 5)
  → leak check    (no AI) a hidden value in an output blocks its download (Stage 6A)
  → edit / regenerate one output → checks again; every version kept
  → review        the Operator submits; a Reviewer approves or sends back with notes (Stage 6B)
  → sign          approve = final files with a QR code + signed record in the record book (Stage 7)
  → verify        public page: record (QR), file fingerprint, or pasted message (Stage 7)
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
| Not in source | **Red wavy underline** on the value, red card | Every number, date, CVE id, IP address, file hash, link, email and phone number in an output must be in the **source text** (the fact sheet does not count: the AI wrote it). `1.2 million` = `1,200,000`, `five` = `5`, `22 Sep` = `22 September` |
| Fact not found | Fact sheet: the fact in **red**, "Not found in source". Output: sentences that use only such facts get a yellow **Linked fact not verified** | The fact's quote could not be found in the source, so the fact may be made up; those sentences do not count as linked in the score |
| Fact sheet does not match | Red banner on Results: **"The fact sheet does not match the source. Do not publish."** | Fewer than half of the fact sheet's quotes were found in the source; every output score and the job score are capped at 50 |
| All clear | The green "Every sentence is linked …" box | Shown only when **every** check passes: no unlinked or unverified sentence, nothing not in the source, all format rules met, no leak, fact sheet matches |
| Consistency | Panel at the top: "All outputs agree", or each mismatch ("the fact sheet says 42 hospitals, but the X thread says 43 hospitals") with a button that opens that sentence | Numbers are compared with their unit word (42 *hospitals*, 72 *hours*) against the fact each sentence is linked to |
| Quality score | Badge on each tab and on the job; hover (or Tab to it) for the explanation in plain words; the card shows the parts | 40 points: sentences linked · 25: quotes found in the source (close = half) · 20: values in the source (each missing one costs a third) · 15: length and format rules (X 280 characters, LinkedIn 3,000, slides 15 words a point, narration 40 words a scene, not cut off …). Job score = average. Saved in the database |
| Edit | **Edit** → a box per text field → **Save and re-check** | Saved as a new version "Edited by human"; all checks run again; empty a box to remove that item; video subtitles are re-timed |
| Versions | **Versions** → **View** an older one (read only, with its own score) | Table `output_versions`; nothing is ever overwritten |
| Regenerate | **Regenerate** writes only that output again from the same fact sheet | Uses the AI (local / cloud); mock mode writes the same text again (same fact sheet, same answer) as a new version. If the AI fails, the previous version stays |

Downloads and the campaign kit always use the **latest** version.

Export fixes in this stage: the PowerPoint footer is measured with the real Hind font and a long
job title is shortened with "…" so the footer stays on one line; in the PDF the indicator table's
value column is wider (and codes shrink a little if still needed), so a SHA-256 fingerprint stays
on one line.

## Safety (Stage 6A)

All rule-based and offline, in `backend/app/safety/`: `scanner.py` (detectors), `shield.py`
(prompt-injection shield), `masking.py` (placeholders and the leak check), `tlp.py` (label rules),
`decisions.py` (the decision log). Try it with the two fictional samples:
`samples/sample-private-data.txt` and `samples/sample-injection.txt`.

| Feature | What you see | How it works |
|---|---|---|
| Sensitivity scanner | Safety check → **What we found**: one row per value, with how many times, which pages, and a choice | Patterns + checks: Aadhaar (12 digits **and** the Verhoeff checksum), PAN, Indian mobiles (+91 / 0 / spaces), email, bank account (after "A/c No"), IFSC, passport, vehicle numbers, GPS, private IPs (10.x, 172.16–31.x, 192.168.x), `.local/.corp/.internal` hosts, `password:` / API keys / tokens / private keys, SECRET / CONFIDENTIAL / RESTRICTED (capitals, or after "Classification:") and "For official use only". Each finding keeps type, text, source, page, character position and risk (high / medium / low) |
| Attack indicators | A separate **Attack indicators** card | Public attacker IPs, CVE ids, file hashes are *not* private: kept in the advisory, left out of public posts by default |
| Choices | Per row: **Hide in public outputs** (default for personal data), **Hide everywhere** (default for passwords/keys), **Keep** | Saved on the job; every change goes into the `safety_decisions` table |
| Source view | The source with every finding highlighted (red = high, saffron = medium, yellow = low, blue = indicator, wavy red = aimed at the AI). Click a row to jump to it | Positions from the scanner |
| TLP label | Right-hand card with the suggestion and why; shown on Results and printed on every exported file | RED / AMBER: LinkedIn, X thread, infographic, video package are switched off with the reason; advisory, executive summary, presentation allowed. GREEN / CLEAR: all allowed. Suggestion: SECRET → RED; other markings, ID numbers, secrets or internal network → AMBER; only contact details or indicators → GREEN; nothing → CLEAR |
| Masking | "What the AI will see" note; the preview line with `[internal address]`; placeholders in the fact sheet | Before **any** AI call, every hidden value becomes a placeholder (`[PHONE-1]`, `[AADHAAR-1]` …). The saved fact sheet keeps them (it shows what the AI saw). After the AI writes, code puts the real value back only in internal outputs for "Hide in public outputs"; public outputs and "Hide everywhere" get a label like `[phone number]` |
| Leak check | Red **Private data found** box on the output, `!` on its tab, downloads blocked, left out of the kit | After every write and every edit, each hidden value is searched for in the output (any spacing: `9876543210` = `98765 43210`) |
| Prompt-injection shield | **Suspicious instructions found** (or "No hidden instructions found") | Phrases like "ignore previous instructions", "you are now", "system prompt", "reveal your …", role tags (`<\|system\|>`, `[INST]`); zero-width / bidi / invisible tag characters (removed; kept inside Indian scripts where they are normal); hidden Word text (white, under 4 pt, "Hidden") and PDF text (invisible, white, under 3 pt), left out of what the AI reads. For each instruction sentence you choose **Remove from what the AI reads** (default, shown struck through) or **Keep (AI told to ignore it)**; the choice is saved in `safety_decisions`. All source text is sent inside `<<<SOURCE … SOURCE>>>` / `<<<FACT SHEET … FACT SHEET>>>` and the prompts say it is data, never instructions |
| Output check | Red wavy underline "Link / Phone number / Email address" | Any link, phone or email in an output that is not in the source itself is flagged |
| Safety section | Results page: label, counts, switched-off outputs, **Decisions** (who, when, what) | `safety_decisions`: scan, each choice change, label, confirmation, start, with the signed-in user's name (Stage 6B; older rows say "Operator"); values are shown only partly in the log |

Limits: rules can miss unusual formats (e.g. a phone number written in words) and can flag things
that only look private; the operator sees everything and decides. White PDF text on a coloured box
can be a false alarm (paste such text in the box instead). A PDF piece that mixes visible and hidden
text is treated as visible.

## Accounts and roles (Stage 6B)

Code: `backend/app/auth/` (`passwords.py`, `accounts.py`, `sessions.py`, `deps.py`),
`backend/app/routes/auth.py`, `review.py`, `admin.py`, `backend/app/audit.py`.

| Role | Can | Cannot |
|---|---|---|
| **Operator** (saffron) | create jobs, safety check, edit, regenerate, retry, download, **Submit for review** | approve; see users or the audit trail |
| **Reviewer** (green) | review queue, open any job, download, **Approve** or **Send back** with notes | change a job; review a job they worked on (created, edited, safety choices, submitted) — *separation of duties* |
| **Admin** (navy) | users, access requests, forgot-password requests, audit trail | see or approve job content |

The roles are checked **in the backend on every request** (`Depends(allow("operator"))` on each
route): **401** = not signed in, **403** = this role may not. Hiding buttons in the web page is only
for convenience. `backend/tests/test_permissions.py` tries every endpoint with every role.

Job states: `ready` → **Submit for review** → `in_review` (locked: nobody can edit) → **Approve**
→ `approved` and **signed** (Stage 7; locked for good), or **Send back** (notes required) →
`sent_back` → the Operator changes it and submits again as **v2**. To change an approved job:
**Start a new version** (needs a new review and a new signature; the new record replaces the old one).

**Accounts**
- *First-time setup*: only while there are no users; makes the first Admin. Then it is closed.
- *Request access* (sign-in page): name, username, Operator or Reviewer, reason, and a password
  (stored only as a hash). An Admin approves (can change the role) or rejects it. Admin accounts are
  made only by an Admin.
- *Forgot password* (offline, no email): sends a request to the Admin. The Admin checks who you are in
  person and clicks **Reset password**: a temporary password (like `tulsi-river-7429-kamal`) is shown
  **once**; you must choose your own at the next sign-in (until then every other request is refused).
- *Passwords*: at least 12 characters, not a very common one, not containing your username or name;
  hashed with **argon2id** (argon2-cffi). **5 wrong passwords lock the account for 15 minutes** (an
  Admin can unlock it sooner). A wrong username takes as long as a wrong password, and the message is
  the same.
- The last active Admin cannot be switched off or demoted.

**Sessions**: a random 256-bit token in a cookie that is `HttpOnly` (page scripts cannot read it),
`SameSite=Strict` (other websites cannot make the browser send it) and `Secure` when served over
HTTPS. The server stores only an HMAC-SHA256 of it (keyed with `APP_SECRET_KEY`). A session ends
after **8 hours**, or **30 minutes** without any request; signing out deletes it; switching a user
off or resetting their password ends all their sessions, and changing your password signs out your
other computers. Every POST/PUT/DELETE must come from one of our own pages (the `Origin` header,
checked against `ALLOWED_ORIGINS`), which stops other websites from sending requests as you.
`APP_SECRET_KEY` is made on first run if empty and saved in `.env`; it is never printed.

**Audit trail** (`audit_log` table, Admin → Audit trail): sign-in, sign-out, failed sign-in,
lockouts, sessions that ended, password changes and resets, user changes, access requests, job
created, every safety decision, edits, regenerate, retry, submit, approve, send back, downloads,
generation finished, and each chain check. Each row stores the SHA-256 of the row before it, and its
own SHA-256 over that plus its content. The database refuses UPDATE and DELETE on the table
(triggers). **Verify chain** works every hash out again and shows the first row that was changed,
removed or added. Limits: someone with the key who deletes the *newest* rows cannot be caught by the
chain alone (Stage 7's signed record book will anchor it); passwords, keys and tokens are never
written to it (a test checks this). Filters: category, search, who, last 24 hours / 7 / 30 days.

## Encryption at rest (Stage 6B)

Everything the app stores is encrypted, so a copied `data/` folder (or a stolen laptop disk) is
unreadable without the key.

| What | How | Code |
|---|---|---|
| The database `data/pramaan.db` | **SQLCipher 4** (AES-256, every page of the file) via the `sqlcipher3` package, which ships its own SQLCipher build for Intel Macs | `backend/app/db.py` |
| Files under `data/jobs/` (uploaded sources, extracted text, exports) | **AES-256-GCM** (`cryptography`): each file starts with `PRMNENC1`, then a fresh 12-byte nonce, then the encrypted bytes and a tag that detects any change | `backend/app/crypto.py` |
| Downloads | Made in memory and sent to the browser; only the encrypted copy is saved | `backend/app/exporters/` |

**The key:** `DB_KEY` in `.env` (64 hex characters = 256 bits). If it is empty, a random one is
made on the first start and written to `.env`; it is never printed or logged. Two separate keys are
derived from it (HKDF-SHA256): one for the database, one for the files.

> **Back up `.env` together with `data/`.** Without `DB_KEY` the data cannot be read by anyone,
> including you. Never change `DB_KEY` on an existing install.

**Upgrading from Stage 6A:** on the first start, the old unencrypted database is copied into an
encrypted one (every table's row count is checked), and the old file is kept as
`data/pramaan.db.plain-backup`. Existing files under `data/jobs/` are encrypted in place (each one
is decrypted again and compared before moving on). After checking that the app works and your jobs
are there, **delete the plain backup** — it is not encrypted:

```bash
rm data/pramaan.db.plain-backup
```

To see for yourself that the database is encrypted (this should fail with "file is not a
database"):

```bash
sqlite3 data/pramaan.db "select count(*) from jobs"
```

**In production** the key would not sit in a file next to the data. It would be given at start-up:
typed by an Admin as a passphrase (stretched with a slow KDF such as Argon2id or PBKDF2 into the
key), or unwrapped by a hardware token (the organisation's HSM / smart card / DSC token via
PKCS#11, or the Mac's Secure Enclave / TPM), and kept only in memory while the app runs. The code
already reads the key in one place (`crypto._master_key`), so only that function would change.

## Signing and verification (Stage 7)

Code: `backend/app/signing/` (`signer.py`, `sign_job.py`, `records.py`, `texts.py`, `messages.py`,
`publish.py`, `qr.py`), `backend/app/routes/records.py`, and the public page in `verify-page/`.

### 1. Signing on Approve (Reviewer)

**Approve & sign** opens the sign dialog (design 26). Then, in one step:

1. The next **record number** is taken: `PRM-<year>-<6 digits>`.
2. The **final files** of every output are made with a real **QR code** in place of the dashed box,
   and the footer says "Approved and signed · Record PRM-…". The QR holds only
   `VERIFY_BASE_URL/?r=<record number>` (`.env`, default `http://localhost:8090`). `.txt` and `.srt`
   files get a "Check it is genuine: …" line instead.
3. **SHA-256** of every final file, and of each output's **normalised text** (spaces, capitals,
   punctuation, emojis and zero-width characters ignored, so a forwarded copy still matches).
4. A **manifest** (record number, job title, TLP, issuing office `ISSUING_OFFICE`, approver name and
   role, time, files and fingerprints, text fingerprints) is **signed** (ECDSA P-256, SHA-256). A second,
   **public** manifest is signed too: for **TLP:RED / AMBER** it has only the record number, date and
   fingerprints, marked "Restricted" (no title, no names, no text). Public records name the approver's
   **role**, not the person.
5. A new, hash-chained entry in the **record book**; the job becomes `approved`.

The signed files are saved encrypted under `data/jobs/<id>/signed/<record>/` and made read-only.
Downloads of an approved job give exactly these bytes; the **signed kit** (.zip) also holds
`record.json` and `public-key.pem`, so anyone can check it with no internet.

**Signers** (`SIGNER` in `.env`), one interface:
- `test` (default): an ECDSA P-256 key made on first use. The private key is stored **encrypted** with
  the Stage 6B file key (`data/keys/test-signer.key`) and never printed or logged. **Not a legal DSC.**
- `dsc`: a Class 3 DSC USB token through PKCS#11 (PyKCS11). **Design only, NOT tested** (no token was
  available): see the notes in `DscSigner` (most Indian DSCs are RSA-2048, the certificate chain must be
  published, …).

### 2. Record book

Reviewer → **Signed records** (design 29); Admin → **Record book** (design 37). The `records` table is
append-only (the database refuses UPDATE and DELETE) and **hash-chained**: each entry stores the hash
of the one before it. **Check the whole chain** re-checks every entry's hash, both signatures, and that
every signed file on disk still has its fingerprint, and shows the **first broken entry**. The Admin can
**Withdraw** a record with a reason: a new signed entry (for TLP:RED / AMBER the public reason is only
"Withdrawn by the issuing office"). A record replaced by a newer version shows "Replaced by …".

### 3. The public "Is this real?" page (`verify-page/`)

Plain HTML + CSS + JS, no backend, no secrets: it reads `records.json` (the public manifests, their
signatures, and a **signed index** of all entries, so a dropped withdrawal is noticed) and
`public-key.pem`, and checks every signature in the browser. Mobile-first, large text, English and
Hindi (हिं button), fonts bundled, works offline once loaded (service worker, on https or localhost).

- `?r=PRM-2026-000001` (what the QR opens): **Genuine** / **Genuine, but replaced** / **Withdrawn** /
  **Not found**, with title, date, issuing office, approver role and the files with fingerprints
  (Restricted records: only number, date, fingerprints).
- **Check a file**: drop it; its SHA-256 is worked out on the device and compared.
- **Paste a message**: see 4.

Signatures are checked with **Web Crypto** when the browser offers it. Browsers only offer it on
`https://` or `localhost`, **not** on a plain `http://192.168.x.x` address (how a phone reaches the demo
laptop), so the page then uses its own built-in SHA-256 and ECDSA P-256 code (`verify.js`). Both paths
are tested.

**Admin → Record book → Export verify bundle** downloads a .zip of the whole site with the latest
records, for one-way (USB) transfer to the public web server. For the demo:

```bash
./scripts/serve-verify.sh
```

builds `data/verify-site/` and serves it on <http://localhost:8090> (and on this Mac's Wi-Fi address).
While it runs, every new signature or withdrawal updates it straight away.

### 4. "Is this real?" message checker (in the app and on the public page)

Paste a forwarded message:
1. **Exact match** (after normalising) with a signed text → "Genuine, matches record X" (or Withdrawn /
   outdated). If several records hold the same text, the newest decides.
2. Otherwise **similarity** with the published texts (5-character shingles, Jaccard): 50% or more →
   "**Changed**: looks like record X", with the **changed words highlighted**.
3. Otherwise "**Not found** — treat as unverified"; with scam signs, "**Not genuine** — looks like a scam".

**Scam signs** (rules, no AI, English and Hindi): asks for an OTP / password / PIN or payment (not "never
share your OTP"), urgent threats ("act within 1 hour", "will be blocked"), links that are not government
sites and not in any record (look-alikes like `gov-alert-update.xyz` are called out), phone numbers not
in any record (1930 and other helplines are fine), asks to install an app. Always shown: **Report cyber
fraud: call 1930 or visit cybercrime.gov.in**. The app version (`/api/check-message`) uses the same
published data, so both give the same answer; a test runs the same messages through the Python and the
JavaScript checker. Pasted messages are not stored or logged.

**Limits:** the test key is not a legal signature; the DSC signer is untested; similarity only knows
texts published for TLP:CLEAR / GREEN social posts; rules can miss a cleverly worded scam or flag an
unusual genuine message (the result says what it found, the person decides); a host could serve an
*older* complete `records.json` (the signed index shows its date) — in production serve it over HTTPS
from the organisation's own server.

### Scan a QR code with your phone (same Wi-Fi)

1. Find this Mac's Wi-Fi address: `ipconfig getifaddr en0` (e.g. `192.168.1.20`).
2. In `.env`, set `VERIFY_BASE_URL=http://192.168.1.20:8090` **before signing** (the address is printed
   inside every QR code), then restart `./scripts/start.sh`.
3. Run `./scripts/serve-verify.sh` (allow incoming connections if macOS asks).
4. Sign a job, open a signed PDF or the infographic on the Mac's screen, and point the iPhone / Android
   **camera app** at the QR code; tap the link. The phone must be on the same Wi-Fi (not a guest
   network that isolates devices).

## API (see <http://localhost:8000/docs> for all details)

Every call except `/api/health` and the sign-in calls needs a session cookie, and every
POST/PUT/DELETE needs an `Origin` header from `ALLOWED_ORIGINS` (browsers send it by themselves).

| Call | Who | What it does |
|---|---|---|
| `GET /api/auth/status` | anyone | does the app need First-time setup? who is signed in? |
| `POST /api/auth/setup` | anyone, only while there are no users | `{"username", "full_name", "password"}`: the first Admin, signed in |
| `POST /api/auth/login` · `/logout` | anyone | `{"username", "password"}` → session cookie; 401 wrong, 423 locked |
| `POST /api/auth/request-access` · `/forgot` | anyone | ask an Admin for an account / a new password |
| `GET /api/auth/me` · `POST /api/auth/change-password` | signed in | `{"current_password", "new_password"}` |
| `POST /api/jobs/{id}/submit` | Operator | `{"notes": ""}`: ready / sent back → in review (refused while an output has private data) |
| `GET /api/review/queue` | Reviewer | jobs waiting (oldest first) and the latest decisions |
| `POST /api/jobs/{id}/review` | Reviewer | `{"decision": "approve" \| "send_back", "notes": "..."}` |
| `GET/POST /api/admin/users`, `PUT /api/admin/users/{id}`, `POST .../reset-password` | Admin | list, add (temporary password shown once), change role / switch off / unlock, reset |
| `GET /api/admin/requests`, `POST .../{id}/approve` · `/reject` | Admin | access and forgot-password requests |
| `GET /api/admin/audit?category=&q=&actor=&days=&offset=` · `POST /api/admin/audit/verify` | Admin | the audit trail; check the hash chain |
| `POST /api/jobs/{id}/review` with `"approve"` | Reviewer | approves **and signs** (Stage 7); optional `"pin"` for a DSC token |
| `GET /api/jobs/{id}/sign-info` | Reviewer | for the sign dialog: signer, outputs, files |
| `POST /api/jobs/{id}/new-version` | Operator | reopen an approved job as a new version |
| `GET /api/records` · `POST /api/records/verify` | Reviewer, Admin | the record book; check chain, signatures and signed files |
| `GET /api/records/{record_no}` · `/qr.png` · `GET /api/records/public-key.pem` | signed in | one record, its QR code, the public key |
| `POST /api/admin/records/{record_no}/withdraw` | Admin | `{"reason": "..."}`: a signed withdrawal entry |
| `GET /api/admin/records/verify-bundle.zip` | Admin | the public verify site with the latest records |
| `POST /api/check-message` | signed in | `{"text": "..."}`: "Is this real?" for a pasted message |

Job calls (Operators change jobs; Reviewers may read them and download):

| Call | What it does |
|---|---|
| `GET /api/options` | the 7 output types and the setting choices |
| `POST /api/jobs` | step 1: form fields `text` and/or `files`, `title`. Reads the sources and scans them; the job comes back as a `draft` with its `safety` report. (Also send `outputs` — repeat per output — and `audience`, `tone`, `objective`, `style`, `detail_level` to do all 3 steps at once with the suggested label and default choices) |
| `PUT /api/jobs/{id}/safety` | step 2: JSON `{"tlp": "AMBER", "choices": {"P1": "hide_all"}}` (choices: `hide_public`, `hide_all`, `keep`); logged in `safety_decisions` |
| `POST /api/jobs/{id}/start` | step 3: JSON `{"outputs": ["advisory"], "settings": {"audience": "Senior officials"}}`; refused (400, with the reason) for public outputs under TLP RED / AMBER |
| `GET /api/jobs` | list jobs |
| `GET /api/jobs/{id}` | status, current step, fact sheet, each output as it finishes, its checks (`quality`, including `leaks`), score, version, the job's `consistency` and `quality_score`, and `tlp`, `safety`, `safety_decisions`, `switched_off` |
| `GET /api/jobs/{id}/sources/{S1}` | the text of one source, page by page (the fact sheet's `start`/`end` are positions in these pages) |
| `PUT /api/jobs/{id}/outputs/{output_id}` | save edits as a new version: JSON `{"fields": [{"path": ["tweets", 0, "text"], "text": "..."}]}` (the editable paths are in each output's `fields`) |
| `POST /api/jobs/{id}/outputs/{output_id}/regenerate` | write one output again from the same fact sheet |
| `GET /api/jobs/{id}/outputs/{output_id}/versions` | every version (number, who made it, score, time); add `/{n}` for one version's text and checks |
| `POST /api/jobs/{id}/retry` | run the failed parts of a job again |
| `GET /api/jobs/{id}/outputs/{output_id}/download?format=pdf` | one file: `docx`, `pdf`, `pptx`, `png`, `srt` or `txt` (each output lists its `formats`); add `&inline=true` to view instead of save |
| `GET /api/jobs/{id}/kit.zip` | the campaign kit: every finished output in one .zip |

Example with curl (from the project folder). First sign in as an Operator; curl keeps the session
cookie in a file (`-c` saves it, `-b` sends it), and `-H Origin` says which page the request is from.
Type the password at the hidden prompt (so it is not saved in your shell history):

```bash
printf "Password: "; read -s PRAMAAN_PW; echo
```

```bash
curl -c /tmp/pramaan-cookies -H "Origin: http://localhost:8000" -H "Content-Type: application/json" -d "{\"username\": \"priya.sharma\", \"password\": \"$PRAMAAN_PW\"}" http://localhost:8000/api/auth/login; unset PRAMAAN_PW
```

```bash
curl -b /tmp/pramaan-cookies -H "Origin: http://localhost:8000" -F files=@samples/sample-ransomware-report.txt -F outputs=x_thread -F outputs=linkedin_post http://localhost:8000/api/jobs
```

Download job 1's campaign kit into the current folder:

```bash
curl -b /tmp/pramaan-cookies -OJ http://localhost:8000/api/jobs/1/kit.zip
```

Sign out (deletes the session on the server) and remove the cookie file:

```bash
curl -b /tmp/pramaan-cookies -H "Origin: http://localhost:8000" -X POST http://localhost:8000/api/auth/logout && rm /tmp/pramaan-cookies
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

`/api/ai/ping` now needs a sign-in: use the dashboard's **Test AI** button. Without signing in it
answers `401 {"detail":"Please sign in."}`.

Backend tests (they always use the mock AI, a temporary folder and test keys, so no model is needed
and your `data/` folder and `.env` are not touched). Stage 6B adds `test_accounts.py`,
`test_sessions.py`, `test_review.py`, `test_permissions.py` (every role × every endpoint),
`test_audit.py` (including changing and deleting rows to prove "Verify chain" finds them),
`test_encryption.py` and `test_no_secrets_in_logs.py`. Stage 7 adds `test_signing.py` (signature
verifies, one changed byte fails, QR files, TLP:RED hides the title, new versions), `test_record_book.py`
(withdraw; changed, re-hashed or deleted entries and changed signed files are found), `test_messages.py`
(exact / changed / unknown / scam signs) and `test_verify_page.py`, which builds a real verify site and
runs the page's own JavaScript with Node (`verify-page/tests/verify.test.mjs`: signatures with and without
Web Crypto, file checks, tampering, and the message checker giving the same answers as Python):

```bash
cd backend && .venv/bin/python -m pytest
```

## AI provider switch

Set `AI_MODE` in `.env`:

- `local` — llama.cpp on this computer (default, offline).
- `mock` — no model; instant answers built from the source by simple rules, for testing.
- `cloud` — Sarvam hosted API, for development only. Put your key in `SARVAM_API_KEY` in `.env`
  (never in code or chat). The hosted API no longer offers `sarvam-30b`; it uses `sarvam-105b`.

Restart the app after changing `.env`.

## Folder map

```
backend/        FastAPI app (app/main.py), settings (app/config.py), database (app/db.py, SQLCipher),
                encryption of stored files (app/crypto.py), audit trail (app/audit.py)
  app/auth/       passwords.py (argon2id, rules), accounts.py, sessions.py, deps.py (role checks) (Stage 6B)
  app/ai/         llm.py (the only file that talks to the model), prompts/*.md, mock_ai.py (the mock AI)
  app/pipeline/   ingest.py, factsheet.py, generate.py, checks.py, output_types.py, runner.py,
                  trace.py, values.py, segments.py, versions.py (Stage 5 checks and versions)
  app/exporters/  real files: docx.py, pdf.py, pptx.py, infographic.py, srt.py, text.py, kit.py
  app/assets/fonts/  Poppins, Hind, IBM Plex Mono (TTF, OFL)
  app/safety/     scanner.py, shield.py, masking.py, tlp.py, decisions.py (Stage 6A, no AI)
  app/routes/     system.py (health, AI ping), jobs.py (jobs API), outputs.py (edit, regenerate, versions, downloads),
                  safety.py (the Safety check), auth.py (sign-in pages), review.py (submit / approve /
                  send back), admin.py (users, requests, audit trail), records.py (record book,
                  verify bundle, "Is this real?")
  app/signing/    signer.py (test key + DSC stub), sign_job.py, records.py (record book), texts.py,
                  messages.py ("Is this real?"), publish.py (verify bundle), qr.py (Stage 7)
frontend/       React + TypeScript + Vite app; design tokens in src/styles/tokens.css;
                sign-in pages in src/pages/auth/, Admin pages in src/pages/admin/
verify-page/    public "Is this real?" page (Stage 7): index.html, app.js (page), verify.js (checks),
                sw.js (offline), fonts/, tests/ (Node)
scripts/        start.sh (app), start-ai.sh (AI model), serve-verify.sh (public verify page on port 8090)
samples/        fictional test files: sample-ransomware-report.txt, sample-private-data.txt (fake
                Aadhaar/PAN/phone/email/IPs/password), sample-injection.txt (hidden instruction)
models/, data/  model files and app data (never committed)
Designs/        screen designs and clickable prototype (reference only)
```
