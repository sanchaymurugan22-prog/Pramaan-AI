#!/usr/bin/env bash
# Serve the public "Is this real?" page for the demo on http://localhost:8090 (the default VERIFY_BASE_URL).
#
# It builds data/verify-site/ from verify-page/ + the latest records.json + public key, then serves it
# as plain static files (the same files the Admin's "Export verify bundle" zip contains). While it runs,
# the backend refreshes data/verify-site/ every time a job is signed or a record is withdrawn.
#
# It listens on all network addresses, so a phone on the same Wi-Fi can open it too:
#   http://<this Mac's Wi-Fi address>:8090   (set VERIFY_BASE_URL in .env to that address before signing,
#   so the QR codes point there; see README "Scan a QR code with your phone").
# Press Ctrl+C to stop.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x "backend/.venv/bin/python" ]; then
  echo "Backend is not installed. Run:  cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

(cd backend && .venv/bin/python -m app.signing.publish "$ROOT/data/verify-site")

ADDRESS=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
echo
echo "Pramaan Verify is on  http://localhost:8090"
[ -n "$ADDRESS" ] && echo "From a phone on the same Wi-Fi:  http://$ADDRESS:8090"
echo "Press Ctrl+C to stop."
exec backend/.venv/bin/python -m http.server 8090 --bind 0.0.0.0 --directory "$ROOT/data/verify-site"
