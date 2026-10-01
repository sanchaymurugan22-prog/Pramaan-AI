# Pramaan AI · 2-minute demo

**Story:** a CERT-In style ransomware report comes in. In two minutes we show that Pramaan AI keeps
private data away from the AI, writes every format from one fact sheet with each sentence traceable,
that the real Indian model did this offline on this laptop, and that the signed result can be checked by
anyone — while a fake WhatsApp alert is caught.

The live part runs with the **mock AI** (instant). The real **Sarvam 30B** run is recorded the evening
before (about 40 minutes on the laptop) and shown from **My jobs** and the **AI models** page.

## Prepare (the evening before, about 45 minutes, mostly waiting)

1. **Accounts.** Start the app (`./scripts/start.sh`), create the Admin at First-time setup, then on
   **Users & access** add an Operator (**Priya Sharma**, EMP-20311, Cyber operations) and a Reviewer
   (**Arjun Mehta**, EMP-10452, Reviewer, *On emergency duty*). Sign in once as each and set their
   passwords.
2. **Letterhead.** As Admin, **Templates** → office name (e.g. "CERT-Demo Cyber Cell") and a logo.
3. **Record the real Sarvam run.** In `.env` set `AI_MODE=local`, restart `./scripts/start.sh`, start
   `./scripts/start-ai.sh` in a second terminal and wait for `server is listening`. Then:

   ```bash
   backend/.venv/bin/python scripts/record-sarvam-run.py --username priya.sharma
   ```

   It runs `samples/sample-ransomware-report.txt` → X thread + LinkedIn post through the real model,
   prints each step, and writes the timing record to `docs/sarvam-runs/`. Leave it to finish.
   (A run recorded on 1 Oct 2026 is in [docs/sarvam-runs/](sarvam-runs/run-2026-10-01-2041.md): fact sheet 24 min,
   X thread 5.7, LinkedIn post 3.5, executive summary 5.7; quality 93.)
4. **Switch to the mock AI for the live part:** `.env` → `AI_MODE=mock`, `MOCK_DELAY_SECONDS=0`; stop
   `start-ai.sh` (frees memory); restart `./scripts/start.sh`. Start `./scripts/serve-verify.sh`.
5. **Windows ready** (signing in on stage wastes time):
   - Browser A (e.g. Safari): signed in as **Priya** on <http://localhost:5173>, on the dashboard.
   - Browser B (e.g. Chrome): signed in as **Arjun** on the review queue.
   - A phone-sized window (or a phone on the same Wi-Fi) with <http://localhost:8090>.
   - The fake message below copied to the clipboard.
6. **A showcase job (mock):** as Priya, run `samples/sample-ransomware-report.txt` with **all 7 outputs**
   (TLP:GREEN, as suggested). Its LinkedIn post has a sentence on purpose with no source (yellow), and it
   has the presentation viewer and the infographic to show.
7. **Rehearse once,** then delete nothing: a second run of the live part simply adds another job.

**Fake message** (paste in step 6):

```
URGENT GOVT CYBER ALERT: Your hospital system is infected. Act within 1 hour or data will be deleted. Verify now at gov-alert-update.xyz and share the OTP sent to your phone.
```

## The demo (2 minutes)

| Time | Do | Say |
|---|---|---|
| **0:00–0:10** | Show Priya's dashboard. | "Government teams turn one report into advisories, briefings, slides and posts — by hand, in a hurry, and fake 'government alerts' spread faster than real ones. Pramaan AI does it offline, with an Indian AI model, and every line is provable." |
| **0:10–0:30** | **New transformation** → **Choose files** → select both `samples/sample-private-data.txt` and `samples/sample-injection.txt` → **Next: safety check**. Point at the 15 findings and the red "Instruction aimed at the AI" card; the suggested label is TLP:AMBER. | "Before any AI reads it, a rule-based scanner finds Aadhaar, PAN, phone numbers, a password — and a hidden line telling the AI to collect passwords. The AI will only see placeholders, and that instruction is cut out. It suggests TLP:AMBER, which switches public posts off." Click **Next**, keep the advisory and the executive summary, **Generate**. |
| **0:30–0:55** | The Results page fills at once (mock). Click a sentence in the **Advisory**: the source trace highlights the quote in the source. (The **Fact sheet** tab shows `[PHONE-1]`-style placeholders: exactly what the AI saw.) Then open the showcase job → **Social posts** → the yellow "Not linked to a fact" sentence. | "Every output is written from one fact sheet. Click any sentence and you see exactly where it came from. A sentence with no source is marked yellow; a number not in the source, red. The quality score counts them." |
| **0:55–1:10** | **My jobs** → the recorded job, *AI used: Sarvam 30B local* → open its X thread. (Optionally Admin → **AI models**: measured speed.) | "This one was written by Sarvam 30B, an Indian model, on this 2017 laptop with no internet — last night, in about 40 minutes for three outputs. On an office server with a GPU it takes seconds." |
| **1:10–1:30** | Back to the new job → **Send for review**. In Browser B (Arjun): **Review** → click a sentence → add a comment → **Approve & sign** → tick → **Sign**. The Signed page shows the QR code. | "A different person must approve — the system enforces it. Approving signs every file: a QR code, a fingerprint, and an entry in a tamper-evident record book." |
| **1:30–1:50** | Phone window: open the record's QR address (or scan it) → **Genuine**. Then **Paste a message** → paste the fake alert → **Check message** → **Not genuine**, with the reasons and *call 1930*. | "Anyone can check: the real advisory is genuine and unchanged. The fake WhatsApp alert is caught — no signature, a look-alike link, an OTP request — and the citizen is told to call 1930. All of this runs on the phone; nothing is uploaded." |
| **1:50–2:00** | Back to the dashboard. | "Offline, Indian AI, every line traced, every file signed. Next: the 22 Indian languages and voices with AI4Bharat models." |

## If something goes wrong

| Problem | Do this |
|---|---|
| A page shows "backend not running" | `./scripts/start.sh` stopped: start it again (5 seconds). |
| The recorded job is missing | Show the record in `docs/sarvam-runs/` and Admin → **AI models** (speed measured from real runs). |
| The QR link does not open on the phone | Open `http://localhost:8090/?r=<record number>` in the phone window instead. |
| Out of time | Skip 0:55–1:10 and say the numbers: "Sarvam 30B, offline, about 40 minutes for three outputs on this laptop." |

## Files used

| File | Shows |
|---|---|
| `samples/sample-private-data.txt` | Fake Aadhaar, PAN, phone, email, bank account, passport, vehicle, GPS, internal IPs, a password, a RESTRICTED marking — 15 findings (checked 1 Oct 2026) |
| `samples/sample-injection.txt` | A hidden instruction to the AI and invisible characters inside words — the shield |
| `samples/sample-ransomware-report.txt` | A clean, realistic report (suggested TLP:GREEN) — the recorded Sarvam run and the showcase job |
