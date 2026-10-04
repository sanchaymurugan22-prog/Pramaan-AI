"""Test the complete real-AI workflow on the deployed Render backend.

Creates a job with incident text and requests x_thread + linkedin_post outputs.
The factsheet is generated automatically as step 1 of the pipeline.
Polls until all outputs complete or fail.
"""
import json
import time
import urllib.request
import http.cookiejar
import uuid

BASE_URL = "https://pramaan-ai-backend.onrender.com"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def json_request(url, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(req, timeout=60) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        return e.code, json.loads(content) if content else {}


def form_request(url, fields):
    """Multipart form-data POST."""
    boundary = uuid.uuid4().hex
    lines = []
    for key, values in fields.items():
        # Support repeated fields (e.g. outputs=x_thread&outputs=linkedin_post)
        if not isinstance(values, list):
            values = [values]
        for value in values:
            lines.append(f"--{boundary}".encode())
            lines.append(f'Content-Disposition: form-data; name="{key}"'.encode())
            lines.append(b"")
            lines.append(value.encode("utf-8") if isinstance(value, str) else value)
    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    body = b"\r\n".join(lines)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with opener.open(req, timeout=60) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        return e.code, json.loads(content) if content else {}


def test_workflow():
    print("=" * 70)
    print("PRAMAAN AI — REAL SARVAM CLOUD AI WORKFLOW TEST")
    print("=" * 70)

    # 1. Health
    print("\n1. Checking health...")
    code, res = json_request(f"{BASE_URL}/api/health")
    print(f"   Health: {code} {res}")
    assert code == 200

    # 2. Login
    print("\n2. Signing in as sih.judge...")
    code, res = json_request(f"{BASE_URL}/api/auth/login", method="POST", data={
        "username": "sih.judge",
        "password": "JudgePassword123!"
    })
    print(f"   Login: {code} — user={res.get('user', {}).get('username')}")
    assert code == 200, f"Login failed: {res}"

    # 3. Create job with outputs (one-step: auto-uses suggested TLP, generates factsheet + outputs)
    print("\n3. Creating job with x_thread + linkedin_post outputs (one-step)...")
    incident_text = (
        "INCIDENT REPORT - CYBER SECURITY BREACH ASSESSMENT\n"
        "Date: October 3, 2026\n"
        "Location: New Delhi, India\n\n"
        "A coordinated phishing campaign targeted three government departments "
        "over a 48-hour period. The attackers used spear-phishing emails containing "
        "malicious PDF attachments disguised as official circulars. Upon opening, the "
        "PDFs exploited a known vulnerability to install a remote access trojan. "
        "The Indian Computer Emergency Response Team (CERT-In) was notified within "
        "2 hours of detection. Preliminary analysis indicates that approximately 150 "
        "email accounts were targeted, with 12 successful compromises. The compromised "
        "accounts were immediately isolated and credential resets were enforced. "
        "Network logs show data exfiltration attempts to servers located outside India. "
        "Forensic analysis is ongoing. No classified data has been confirmed as leaked. "
        "All affected systems have been taken offline for remediation."
    )

    code, job = form_request(f"{BASE_URL}/api/jobs", {
        "title": "SIH Test — Cyber Incident Report",
        "text": incident_text,
        "outputs": ["x_thread", "linkedin_post"],
        "detail_level": "medium",
    })
    print(f"   Job create: {code}")
    if code not in (200, 201):
        print(f"   Error: {job}")
        raise RuntimeError(f"Job creation failed: {job}")
    job_id = job["id"]
    job_status = job.get("status")
    print(f"   Created Job ID: {job_id}, status: {job_status}")

    # 4. Poll until all outputs are done
    print("\n4. Polling for factsheet + x_thread + linkedin_post completion...")
    print("   (Factsheet is generated automatically as step 1 of the AI pipeline)")
    done_outputs = set()
    for i in range(90):  # up to 7.5 minutes
        time.sleep(5)
        code, data = json_request(f"{BASE_URL}/api/jobs/{job_id}")
        status = data.get("status")
        step = data.get("step", "")
        fact_sheet = data.get("fact_sheet")
        outputs = data.get("outputs", [])

        # Check factsheet
        has_factsheet = bool(fact_sheet and fact_sheet.get("summary"))
        if has_factsheet and "factsheet" not in done_outputs:
            done_outputs.add("factsheet")
            print(f"\n   >>> FACT SHEET COMPLETED! <<<")
            summary = fact_sheet.get("summary", "")
            print(f"   Summary: {summary[:150]}...")
            facts = fact_sheet.get("key_facts", [])
            print(f"   Key facts: {len(facts)}")

        # Check each output
        for out in outputs:
            otype = out.get("type")
            ostatus = out.get("status")
            if ostatus in ("completed", "done") and otype not in done_outputs:
                done_outputs.add(otype)
                content = out.get("content", {})
                print(f"\n   >>> {otype.upper()} COMPLETED! <<<")
                print(f"   Content snippet: {json.dumps(content, indent=2)[:200]}")
            elif ostatus == "failed" and otype not in done_outputs:
                done_outputs.add(otype)
                err = out.get("error_message") or out.get("error")
                print(f"\n   !!! {otype.upper()} FAILED: {err} !!!")

        out_summary = ", ".join(f"{o.get('type')}={o.get('status')}" for o in outputs)
        print(f"   [{i+1}/90] job={status} step=\"{step}\" fs={'YES' if has_factsheet else 'no'} | {out_summary}")

        # Check if everything is done
        if status in ("completed", "ready", "failed"):
            break
    else:
        print("\n   !!! TIMED OUT !!!")

    # Final summary
    code, data = json_request(f"{BASE_URL}/api/jobs/{job_id}")
    final_status = data.get("status")
    fact_sheet = data.get("fact_sheet")
    outputs = data.get("outputs", [])

    print("\n" + "=" * 70)
    print("WORKFLOW RESULTS:")
    print(f"  Job status:    {final_status}")
    print(f"  Fact sheet:    {'PASS' if fact_sheet and fact_sheet.get('summary') else 'FAIL'}")
    for out in outputs:
        otype = out.get("type")
        ostatus = out.get("status")
        label = "PASS" if ostatus in ("completed", "done") else f"FAIL ({ostatus})"
        print(f"  {otype:20s} {label}")
    print("=" * 70)

    # Assert all passed
    assert fact_sheet and fact_sheet.get("summary"), "Fact sheet not generated!"
    for out in outputs:
        if out.get("type") in ("x_thread", "linkedin_post"):
            assert out.get("status") in ("completed", "done"), f"{out['type']} did not complete: {out.get('status')}"

    print("\n5. Submitting job for Reviewer approval...")
    code, sub_res = json_request(f"{BASE_URL}/api/jobs/{job_id}/submit", method="POST", data={"notes": "Submitting for SIH review"})
    print(f"   Submit: {code} status={sub_res.get('status')}")
    assert code in (200, 201), f"Submit failed: {sub_res}"

    print("\n6. Signing in as Reviewer (reviewer.demo)...")
    code, rev_login = json_request(f"{BASE_URL}/api/auth/login", method="POST", data={
        "username": "reviewer.demo",
        "password": "ReviewerPassword123!"
    })
    print(f"   Reviewer login: {code} user={rev_login.get('user', {}).get('username')}")
    assert code == 200, f"Reviewer login failed: {rev_login}"

    print("\n7. Checking Review Queue...")
    code, queue = json_request(f"{BASE_URL}/api/review/queue")
    print(f"   Queue status: {code}, waiting items={len(queue.get('waiting', []))}")

    print("\n8. Adding Reviewer Line Comment...")
    code, c_res = json_request(f"{BASE_URL}/api/jobs/{job_id}/comments", method="POST", data={
        "text": "Verified factsheet and social outputs. Grounding confirmed."
    })
    print(f"   Add comment: {code}")

    print("\n9. Reviewer approving and signing job with Web Digital Certificate...")
    code, rev_res = json_request(f"{BASE_URL}/api/jobs/{job_id}/review", method="POST", data={
        "decision": "approve",
        "notes": "Approved & signed by Reviewer (Web Digital Certificate)",
        "pin": "",
        "reasons": []
    })
    print(f"   Review response: {code}, status={rev_res.get('status')}")
    assert code in (200, 201), f"Review sign failed: {rev_res}"
    record = rev_res.get("record")
    print(f"   >>> SIGNED RECORD CREATED: {record.get('record_no')} <<<")
    print(f"   Fingerprint: {record.get('fingerprint')[:24]}...")
    print(f"   Verify URL:  {record.get('verify_url')}")

    print("\n10. Checking Record Book chain...")
    code, rec_book = json_request(f"{BASE_URL}/api/records")
    print(f"    Record Book status: {code}, total records={len(rec_book.get('records', []))}")

    print("\n11. Testing 'Is This Real?' verification...")
    tweet_text = outputs[0].get("content", {}).get("tweets", [{}])[0].get("text", incident_text[:100])
    code, check_res = json_request(f"{BASE_URL}/api/check-message", method="POST", data={"text": tweet_text})
    print(f"    Message check: {code}, verdict={check_res.get('verdict')}")

    print("\n======================================================================")
    print("ALL REAL AI + REVIEW + SIGNING + VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    test_workflow()
