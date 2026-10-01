"""Record a REAL Sarvam 30B run before a demo (Stage 10).

The local model needs about 25 minutes for the sample report on the dev laptop, too long to show live.
Run this the evening before: it makes the job through the normal API (so it appears in My jobs, marked
"AI used: Sarvam 30B local"), follows it to the end, and writes a timing record to docs/sarvam-runs/.

Needs: AI_MODE=local in .env, ./scripts/start-ai.sh and ./scripts/start.sh running, an Operator account.

    backend/.venv/bin/python scripts/record-sarvam-run.py --username priya.sharma
    backend/.venv/bin/python scripts/record-sarvam-run.py --username priya.sharma --outputs x_thread,linkedin_post,executive_summary

The password is asked for at a hidden prompt (never on the command line, never saved).
"""

import argparse
import getpass
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default="http://localhost:8000", help="the backend (default %(default)s)")
    parser.add_argument("--username", required=True, help="an Operator's username, employee ID or email")
    parser.add_argument("--source", default=str(ROOT / "samples" / "sample-ransomware-report.txt"))
    parser.add_argument("--outputs", default="x_thread,linkedin_post", help="comma-separated (default %(default)s)")
    parser.add_argument("--title", default="Ransomware attack on hospital networks (recorded Sarvam 30B run)")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.url, headers={"Origin": args.url}, timeout=120)
    try:
        health = client.get("/api/health").json()
    except httpx.HTTPError:
        print(f"The backend is not running at {args.url}. Start ./scripts/start.sh first.")
        return 1
    if health.get("ai_mode") != "local":
        print(f"AI_MODE is {health.get('ai_mode')!r}: set AI_MODE=local in .env and restart ./scripts/start.sh.")
        return 1
    password = getpass.getpass(f"Password for {args.username}: ")
    signed = client.post("/api/auth/login", json={"username": args.username, "password": password})
    del password
    if signed.status_code != 200:
        print("Could not sign in:", signed.json().get("detail"))
        return 1
    ping = client.get("/api/ai/ping").json()
    if not ping.get("ok"):
        print("The AI does not answer:", ping.get("error"), "\nStart ./scripts/start-ai.sh and wait for 'server is listening'.")
        return 1

    source = Path(args.source)
    started = time.time()
    created = client.post("/api/jobs", data={"title": args.title, "outputs": args.outputs.split(",")},
                          files={"files": (source.name, source.read_bytes(), "text/plain")})
    if created.status_code != 201:
        print("Could not start the job:", created.json().get("detail"))
        return 1
    job_id = created.json()["id"]
    print(f"Job #{job_id:04d} started. Following it (Ctrl+C stops watching; the job carries on).")

    steps, last = [], None
    while True:
        job = client.get(f"/api/jobs/{job_id}").json()
        step = job["step"].split(" · ")[0] if job["step"] else job["status"]
        if step != last:
            steps.append((round(time.time() - started), step))
            print(f"  {steps[-1][0] // 60:3d}:{steps[-1][0] % 60:02d}  {step}")
            last = step
        if job["status"] != "generating":
            break
        time.sleep(10)
    total = time.time() - started

    out_dir = ROOT / "docs" / "sarvam-runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"run-{datetime.now():%Y-%m-%d-%H%M}.md"
    lines = [
        f"# Recorded Sarvam 30B run · job #{job_id:04d}", "",
        f"- When: {datetime.now():%d %b %Y, %H:%M}", f"- Source: `{source.name}` ({len(source.read_text())} characters)",
        f"- Model: {ping.get('model')} via {ping.get('base_url')}", f"- Result: **{job['status']}**, quality {job['quality_score']}",
        f"- Total time: **{total / 60:.1f} minutes**", "",
        "| Step | Time | Tokens written | Tokens per second |", "|---|---|---|---|",
    ]
    sheet = job.get("fact_sheet") or {}
    if sheet:
        lines.append(f"| Fact sheet | {sheet.get('seconds', 0) / 60:.1f} min | — | — |")
    for output in job["outputs"]:
        seconds, tokens = output.get("seconds") or 0, output.get("tokens") or 0
        rate = f"{tokens / seconds:.2f}" if seconds and tokens else "—"
        lines.append(f"| {output['label']} ({output['status']}) | {seconds / 60:.1f} min | {tokens or '—'} | {rate} |")
    lines += ["", "Progress as it happened (minutes:seconds after the start):", ""]
    lines += [f"- {t // 60}:{t % 60:02d} {s}" for t, s in steps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"{path.stem}.json").write_text(json.dumps({"job": job_id, "total_seconds": round(total),
                                                           "steps": steps}, indent=1), encoding="utf-8")
    print(f"\nDone in {total / 60:.1f} minutes. Record written to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
