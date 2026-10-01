# Pramaan AI · User guide

The detailed guide to every part of Pramaan AI, written stage by stage as the app was built. The
[README](../README.md) has the overview, installation, quick start and troubleshooting;
[ARCHITECTURE.md](ARCHITECTURE.md) explains the design; [DEMO_SCRIPT.md](DEMO_SCRIPT.md) is the
2-minute demo; [TEST_REPORT.md](TEST_REPORT.md) lists how every feature was tested.

Contents: How it works · Downloads · Trust · Safety · Accounts and roles · Encryption at rest ·
Signing and verification · Operator screens · All screens for every role · API · About the AI model

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
- *Request access* (sign-in page): name, employee ID (Stage 9B; it becomes the username), official email,
  division, Operator or Reviewer, preferred language, and a password (stored only as a hash). An Admin approves (can change the role) or rejects it. Admin accounts are
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

## Operator screens (Stage 9A)

Try each one with the mock AI (`AI_MODE=mock` in `.env`, then `./scripts/start.sh`), signed in as an
Operator. A Reviewer account is needed for the review steps.

| Screen | Where | What to try |
|---|---|---|
| Dashboard (08) | **Dashboard** | Numbers are real (jobs this week, outputs approved, hours saved is an *estimate*, languages). "Needs your attention" lists jobs sent back (with the Reviewer's note), private data found, sentences not linked to the source, watch-folder drafts, and jobs ready to send. |
| New transformation (09–11) | **New transformation** | Unchanged steps, now with the job number; a watch-folder draft shows a **Watch folder** badge and its kit is ticked in advance. **Generate** opens the live progress. |
| Generating (12) | after Generate, or **See live progress** | The fact sheet, each output (Queued → Writing → Ready, with times), a progress bar, the time left, and a live preview of the latest finished text. You can leave: a notification says when it is done. |
| Results (13–18) | click a job | Tabs: Advisory, Executive summary (as a page, with words, reading time and "traced x of y"), Presentation (slide viewer, speaker notes, words on slide), Video package (storyboard: scenes, on-screen text, narration, subtitles), Social posts (LinkedIn + X thread as they will look, characters, **Copy**, what was hidden, public-release check), Infographic (image + headline, numbers, steps), Fact sheet. Arrow keys move between tabs. The source trace, warnings and quality score stay on the right for every tab. |
| Campaign kit (19) | **Campaign kit** on a job | Tick the outputs to put in the .zip; once signed, the file sizes and "Approved and signed by …" show. |
| My jobs (20) | **My jobs** | Job number, version, status, TLP, AI used (Mock / Sarvam 30B local), quality. Search (title, `#0012`, source file name), status tabs, last 7/30/90 days, sharing level, 10 per page. |
| Version compare (21) | **Compare versions** on a job with v2 | Send a job back as a Reviewer, edit an output (e.g. change "42 hospitals" to "57"), submit again: the page shows *Hospitals 42 → 57*, list changes, and every changed sentence with added (green, underlined) and removed (red, struck through) words. Pick any two versions, including the first AI draft. |
| Emergency alert (22) | **Emergency alert** | Type a short alert; the character count (160 = one SMS) and the public-release check (no panic words, no shouting, no private data; helplines like 1930 are fine) update as you type. **Send for fast-track approval** makes a TLP:CLEAR job; when its outputs are ready it goes to the Reviewers by itself, first in their queue. Other languages and voice come in Stage 8. |
| Watch folder (23) | **Watch folder** | See below. |
| Notifications (40) | the bell, or **Notifications** | Job finished, sent back (with notes), approved, signed (record number), watch-folder drafts; Reviewers: submitted, emergency alert. All / Unread, Mark all as read. In the app only: nothing is emailed. |

The **search box** at the top finds jobs (title or number), sources (file name, or the first 8+ characters
of a SHA-256 fingerprint) and records (record number or title). Use ↓ ↑ and Enter, or click.

### Watch folder

1. **Watch folder** → switch it on. The folder is `data/watch/incoming` (make others with **New folder**;
   only folders inside `data/watch/` are allowed). Pick the **kit to prepare**.
2. Copy a report into the folder, for example:

```bash
cp samples/sample-private-data.txt data/watch/incoming/cert-report-0929.txt
```

3. Within a minute (`WATCH_INTERVAL_SECONDS` in `.env`, default 60), or at once with **Check now**, it
   shows "Ready for you", the menu shows a badge, and the dashboard lists it.
4. **Open** it: it is a **draft waiting at the Safety check**. The AI has not run. You check what the
   scanner found, choose the sharing label (never set automatically) and press Generate yourself.

Files that are not .txt / .pdf / .docx, files still being copied, and (with "Skip duplicates") files that
are exactly the same as an earlier job's source are listed but not drafted. Pramaan never moves, changes
or deletes your files; its own copy is encrypted like every source.

### Accessibility (GIGW / WCAG 2.1 AA)

- **Keyboard:** everything works without a mouse. The first Tab shows **Skip to main content**; result
  tabs use the arrow keys; the search list uses ↓ ↑ Enter Escape; slides and scenes are buttons.
- **Focus:** a 3-pixel navy ring on every control (at least 3:1 against every background).
- **Labels:** every field, switch and icon button has a name; badges say "2 drafts waiting", the bell
  says "Notifications, 3 unread".
- **Contrast:** all text at least 4.5:1 (large text 3:1); white-on-saffron badges were changed to the
  darker saffron for this.
- **200% zoom:** at 200% on a laptop (720 pixels wide) the menu becomes a **Menu** button that opens a
  drawer (Escape closes it); pages reflow into one column with no sideways scrolling.
- **Not colour alone:** statuses have an icon and a word, scores a number, unlinked sentences a tag,
  compare uses underline / strike-through (and "added" / "removed" for screen readers), switches say On / Off.
- After moving to another page, focus goes to the page, so screen readers start reading there.

## All screens for every role (Stage 9B)

With the mock AI (`AI_MODE=mock`), start the app and try each role. A test account for each role can be
made by the Admin on **Users & access** (the person signs in with the temporary password shown once).

**Start (designs 01–07)**

| Screen | What to try |
|---|---|
| Splash (01) | Opens once per browser (or at `#/welcome`). The bar fills when the backend answers; **Get started**. |
| Language (02) | Pick any of the 23 languages. Saved in this browser, and used for "Preferred language" when asking for access. The app's own words stay English until Stage 8. |
| Sign in (03) | Type your **username, employee ID or official email** (any case). |
| Request access (04) | Full name, **employee ID**, official email, **division**, role, password, preferred language, the acceptable-use box. The employee ID becomes the username. |
| Forgot password (05) | Username or employee ID; the Admin resets it. |
| Pending (06) | Shows your details and which Admin can approve. Sign in with your employee ID once approved. |
| First-time setup (07) | Shows **this computer's real memory, processors, free disk** and the AI in use; makes the first Admin (with employee ID). |

**Reviewer (designs 24–29)**

| Screen | What to try |
|---|---|
| Review queue (24) | Waiting, signed today, **average review time** and sent back this week, all measured. Emergency alerts first; filter All / Emergency / Kits. The signing key card and today's signed records. |
| Review a kit (25) | **Click any sentence**: its source shows on the right, and you can **comment on that line**. Outputs with notes have a ⚠ mark. **Automatic checks** list what the app already checked. *Take back* a comment while the review is open. |
| Sign (26) → Signed (27) | **Approve & sign** → tick the box → **Sign N files** → the Signed page with the record's QR code, fingerprint and what happened next. |
| Send back (28) | Pick reasons, see each line comment next to **what the source says**, add a whole-job comment, write a note. The Operator gets a notification, and on the job a **Line comments from the Reviewer** card with **Show the line** for each. |
| Signed records (29) | Search, filter, check the chain, **Export list** (CSV). |

**Admin (designs 30–39)**

| Screen | What to try |
|---|---|
| Overview (30) | Active users by role, jobs this month, documents signed, fake or edited messages caught by "Is this real?" (counts only, never the messages), **this computer** (processor load, memory, disk, encryption), approve requests here, latest security events. |
| Users & access (31, 32) | Employee ID, email, division, DSC token, emergency duty, status, last active. **Add user** / **Edit**: the same details; a Reviewer on the **emergency duty roster** is told first about emergency alerts. |
| Audit trail (33) | Filters as before; **Export log with hashes** (CSV) so the chain can be checked outside the app. |
| AI models (34) | Which AI is in use (set by `AI_MODE` in `.env`, not from the page), the planned models, and **speeds measured from real jobs** on this computer. **Run a speed test** asks the AI for a short answer and times it. |
| Templates (35) | The built-in template of each output, and **your letterhead**: type the **office name** and **upload a logo** (PNG / JPEG, up to 2 MB). From then on every PDF, Word, PowerPoint, PNG and text file carries them, and the public verify page says "Issued by" that office. |
| Security & policies (36) | Switch scanner checks on or off (a warning if you switch one off), add **classification words** (e.g. INTERNAL ONLY: found in every new source), **sign out after 15 / 30 / 60 minutes**, **lock after 3 / 5 / 10 wrong passwords**. These really apply, and every change is in the audit trail. |
| Record book (37) | As in Stage 7, plus Export list. |
| Public verify page (38) | Its address, what it holds and never holds, **Export update file** for the USB copy. |
| Updates & backup (39) | **Back up now**: one .zip in `data/backups/` with a consistent copy of the encrypted database and every (encrypted) file, made while the app runs. **Keep a copy of `.env` separately**: the backup cannot be read without `DB_KEY`. The README in the zip explains how to restore. Installing update packages comes in Stage 10. |

**Everyone**

| Screen | What to try |
|---|---|
| Notifications (40) | As in 9A. Switch kinds off on Profile & settings. |
| Profile & settings (41) | Your details (changed by an Admin), **app language**, **default output languages**, **text size** (whole app larger) and **high contrast**, notification switches, change password, sign out. |
| Help | A short guide for your role, keyboard keys, what to do if something is wrong. Works offline. |
| You don't have access | Open a page of another role (e.g. `#/admin/security` as an Operator): a friendly page with a link home. The backend refuses its data anyway (403). Unknown addresses say the page does not exist. |

**Public verify page (42–46, `verify-page/`)**: on a phone browser that can read QR codes (Chrome on
Android, over https or localhost), **Scan with this phone's camera** reads the QR code live (nothing is
uploaded); elsewhere the steps for the phone's own camera app are shown. Genuine results show "Changed
since? No"; fake ones have **Warn my family and friends** (shares a short warning, not the scam message).

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
| `GET /api/notifications` (`?unread=true`) · `/count` · `POST .../{id}/read` · `/read-all` | signed in | my notifications (Stage 9A); `count` also gives `watch_drafts` |
| `GET /api/search?q=` | signed in | jobs, sources and records (Admins: records only) |
| `GET /api/dashboard` | Operator | dashboard numbers and "Needs your attention" |
| `GET/PUT /api/watch`, `POST /api/watch/folders` · `/check` | Operator | watch folder settings, make a folder, check now |
| `POST /api/alerts/check` · `POST /api/alerts` | Operator | emergency alert: live check; make the alert job (fast-track review) |
| `GET /api/auth/options` · `GET /api/auth/computer` | anyone (computer: only before setup) | languages and divisions; this computer's memory, cores, disk and AI |
| `GET/PUT /api/profile` | signed in | my details; change my language and preferences only |
| `GET/POST /api/jobs/{id}/comments`, `DELETE .../{cid}` | Operator + Reviewer / Reviewer | line comments (add and take back: Reviewer, while in review) |
| `POST /api/jobs/{id}/review` with `"reasons"` | Reviewer | send-back reasons: Facts need checking, Language quality, Tone, Sensitive detail, Formatting |
| `GET /api/admin/overview` · `GET /api/admin/ai` · `POST /api/admin/ai/speed-test` | Admin | overview numbers; AI and measured speed; speed test |
| `GET/PUT /api/admin/security` | Admin | security policy (scanner switches, classification words, inactivity, lockout) |
| `GET/PUT /api/admin/letterhead`, `POST/DELETE /api/admin/letterhead/logo`, `GET /api/letterhead/logo.png` | Admin (logo image: signed in) | office name and logo on exported files |
| `GET /api/admin/public-page` · `GET/POST /api/admin/backups` · `GET /api/admin/backups/{name}` | Admin | public page information; list / make / download backups |

Job calls (Operators change jobs; Reviewers may read them and download):

| Call | What it does |
|---|---|
| `GET /api/options` | the 7 output types and the setting choices |
| `POST /api/jobs` | step 1: form fields `text` and/or `files`, `title`. Reads the sources and scans them; the job comes back as a `draft` with its `safety` report. (Also send `outputs` — repeat per output — and `audience`, `tone`, `objective`, `style`, `detail_level` to do all 3 steps at once with the suggested label and default choices) |
| `PUT /api/jobs/{id}/safety` | step 2: JSON `{"tlp": "AMBER", "choices": {"P1": "hide_all"}}` (choices: `hide_public`, `hide_all`, `keep`); logged in `safety_decisions` |
| `POST /api/jobs/{id}/start` | step 3: JSON `{"outputs": ["advisory"], "settings": {"audience": "Senior officials"}}`; refused (400, with the reason) for public outputs under TLP RED / AMBER |
| `GET /api/jobs` | list jobs; filters `?q=` (title, `#0012`, source file), `?status=draft,in_review`, `?tlp=AMBER`, `?days=30` |
| `GET /api/jobs/{id}` | status, current step, fact sheet, each output as it finishes, its checks (`quality`, including `leaks`), score, version, the job's `consistency` and `quality_score`, and `tlp`, `safety`, `safety_decisions`, `switched_off` |
| `GET /api/jobs/{id}/sources/{S1}` | the text of one source, page by page (the fact sheet's `start`/`end` are positions in these pages) |
| `PUT /api/jobs/{id}/outputs/{output_id}` | save edits as a new version: JSON `{"fields": [{"path": ["tweets", 0, "text"], "text": "..."}]}` (the editable paths are in each output's `fields`) |
| `POST /api/jobs/{id}/outputs/{output_id}/regenerate` | write one output again from the same fact sheet |
| `GET /api/jobs/{id}/outputs/{output_id}/versions` | every version (number, who made it, score, time); add `/{n}` for one version's text and checks |
| `POST /api/jobs/{id}/retry` | run the failed parts of a job again |
| `GET /api/jobs/{id}/outputs/{output_id}/download?format=pdf` | one file: `docx`, `pdf`, `pptx`, `png`, `srt` or `txt` (each output lists its `formats`); add `&inline=true` to view instead of save |
| `GET /api/jobs/{id}/kit.zip` | the campaign kit: every finished output in one .zip (`?outputs=advisory,x_thread` for some only) |
| `GET /api/jobs/{id}/kit-info` | what the kit holds (file sizes once signed) |
| `GET /api/jobs/{id}/compare?left=1&right=2` | two versions side by side (0 = first AI draft); numbers and lists that changed |

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

`scripts/start-ai.sh` runs (with `-m models/sarvam-30b-Q4_K_M.gguf-00001-of-00006.gguf` instead of
`-hf ... --offline` when `scripts/install.sh` put the model files in `models/`):

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
