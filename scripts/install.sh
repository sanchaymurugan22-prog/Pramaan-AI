#!/usr/bin/env bash
# Install Pramaan AI from the OFFLINE BUNDLE (made by scripts/make-offline-bundle.sh). No internet is used.
#
#   ./scripts/install.sh                     uses ./offline-bundle
#   ./scripts/install.sh /Volumes/USB/pramaan-bundle
#   ./scripts/install.sh --no-model          skip the model even if the bundle has it (AI_MODE=mock)
#   ./scripts/install.sh --skip-tests        do not run the backend tests at the end
#
# Steps: check this computer (platform, Python 3.12, Node, RAM, disk, ports) -> check every file of the
# bundle against SHA256SUMS -> Python packages into backend/.venv -> frontend packages -> llama.cpp into
# ~/llama -> the model into models/ -> the language and voice models (Stage 8) -> .env -> a quick test. Safe to run again: finished steps are redone
# quickly, and an existing .env is never overwritten.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BUNDLE="$ROOT/offline-bundle"
WITH_MODEL=1
RUN_TESTS=1
for arg in "$@"; do
  case "$arg" in
    --no-model) WITH_MODEL=0 ;;
    --skip-tests) RUN_TESTS=0 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $arg (see --help)"; exit 1 ;;
    *) BUNDLE="$(cd "$arg" 2>/dev/null && pwd || echo "$arg")" ;;
  esac
done

STEP=0
say() { STEP=$((STEP + 1)); printf '\n[%s] %s\n' "$STEP" "$*"; }
ok() { printf '    OK   %s\n' "$*"; }
warn() { printf '    NOTE %s\n' "$*"; }
fail() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

# ---- 1. this computer ----------------------------------------------------------------------------------
say "Checking this computer"
[ -f "$BUNDLE/MANIFEST.txt" ] || fail "No offline bundle at $BUNDLE. Make one with scripts/make-offline-bundle.sh on a
         computer with internet, copy it here, and give its folder: ./scripts/install.sh /path/to/bundle"
PLATFORM="$(uname -s)-$(uname -m)"
BUNDLE_PLATFORM="$(sed -n 's/^platform: //p' "$BUNDLE/MANIFEST.txt")"
[ "$PLATFORM" = "$BUNDLE_PLATFORM" ] || fail "This bundle was made for $BUNDLE_PLATFORM, but this computer is $PLATFORM.
         Make the bundle on a computer of the same kind."
ok "platform $PLATFORM matches the bundle"

PYTHON=""
for candidate in python3.12 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 /usr/local/bin/python3.12; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
done
[ -n "$PYTHON" ] || fail "Python 3.12 is not installed. Install it from its offline installer (python.org .pkg), then run this again."
BUNDLE_PY="$(sed -n 's/^python: //p' "$BUNDLE/MANIFEST.txt")"
ok "Python $("$PYTHON" -V 2>&1 | cut -d' ' -f2) (bundle made with $BUNDLE_PY)"
command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || fail "Node and npm are not installed. Install Node LTS from its offline installer (nodejs.org .pkg)."
ok "Node $(node -v), npm $(npm -v)"

if [ "$(uname -s)" = Darwin ]; then
  RAM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
else
  RAM_GB=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
fi
HAS_MODEL=0
[ -d "$BUNDLE/models" ] && [ "$WITH_MODEL" = 1 ] && HAS_MODEL=1
HAS_LANG=0
[ -d "$BUNDLE/lang-models" ] && HAS_LANG=1
if [ "$RAM_GB" -lt 8 ]; then
  fail "Only $RAM_GB GB of memory. Pramaan AI needs at least 8 GB (16 GB or more for the local AI)."
elif [ "$RAM_GB" -lt 16 ] && [ "$HAS_MODEL" = 1 ]; then
  warn "$RAM_GB GB of memory: the 18 GB model will not fit well. Use AI_MODE=mock, or install with --no-model."
elif [ "$RAM_GB" -lt 32 ] && [ "$HAS_MODEL" = 1 ]; then
  warn "$RAM_GB GB of memory: the local AI works but is slow (about 1.4 words a second on a 16 GB laptop)."
else
  ok "$RAM_GB GB of memory"
fi

NEEDED_GB=3
[ "$HAS_MODEL" = 1 ] && NEEDED_GB=22
[ "$HAS_LANG" = 1 ] && NEEDED_GB=$((NEEDED_GB + 1))
FREE_GB=$(df -Pk "$ROOT" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
[ "$FREE_GB" -ge "$NEEDED_GB" ] || fail "Not enough free disk space: $FREE_GB GB free here, $NEEDED_GB GB needed."
ok "$FREE_GB GB free disk space (needs $NEEDED_GB GB)"

# Ports: backend 8000, frontend 5173, AI 8081, public verify page 8090
BUSY=""
for port in 8000 5173 8081 8090; do
  pid=$(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1 || true)
  if [ -n "$pid" ]; then BUSY="$BUSY $port ($(ps -o comm= -p "$pid" 2>/dev/null | xargs basename 2>/dev/null || echo "process $pid"))"; fi
done
if [ -n "$BUSY" ]; then
  warn "these ports are in use:$BUSY. Installing is fine; stop those programs before starting Pramaan AI
         (an old Pramaan AI on 8000/5173 is stopped by scripts/start.sh itself)."
else
  ok "ports 8000, 5173, 8081 and 8090 are free"
fi

# ---- 2. the bundle is complete and unchanged ------------------------------------------------------------
say "Checking every file of the bundle (SHA-256)$([ "$HAS_MODEL" = 1 ] && echo '; the model takes a few minutes')"
cd "$BUNDLE"
if [ "$HAS_MODEL" = 1 ]; then
  shasum -a 256 -c --quiet SHA256SUMS || fail "Some files of the bundle are damaged or missing (listed above). Copy the bundle again."
else
  grep -v ' ./models/' SHA256SUMS | shasum -a 256 -c --quiet - || fail "Some files of the bundle are damaged or missing (listed above). Copy the bundle again."
fi
cd "$ROOT"
cmp -s "$BUNDLE/node/package-lock.json" frontend/package-lock.json \
  || fail "The bundle was made for another version of the code (frontend/package-lock.json differs). Make it again."
ok "$(wc -l < "$BUNDLE/SHA256SUMS" | tr -d ' ') files checked"

# ---- 3. Python packages -----------------------------------------------------------------------------------
say "Python packages (backend/.venv)"
[ -x backend/.venv/bin/python ] || "$PYTHON" -m venv backend/.venv
backend/.venv/bin/pip install --quiet --no-index --find-links "$BUNDLE/python/wheels" -r backend/requirements.txt \
  || fail "Installing the Python packages failed (see above)."
ok "$(backend/.venv/bin/pip list 2>/dev/null | tail -n +3 | wc -l | tr -d ' ') packages installed"

# ---- 4. frontend packages ---------------------------------------------------------------------------------
say "Frontend packages (frontend/node_modules)"
(cd frontend && npm ci --offline --cache "$BUNDLE/node/npm-cache" --no-audit --no-fund --loglevel=error >/dev/null) \
  || fail "Installing the frontend packages failed (see above)."
ok "installed from the bundle"

# ---- 5. llama.cpp ------------------------------------------------------------------------------------------
say "llama.cpp (~/llama)"
if cmp -s "$BUNDLE/llama/llama-server" "$HOME/llama/llama-server" 2>/dev/null; then
  ok "the same llama.cpp is already in ~/llama: kept"
else
  # never overwrite a llama-server that is running (macOS stops a program whose file changes)
  if pgrep -f "$HOME/llama/llama-server" >/dev/null 2>&1; then
    fail "llama-server from ~/llama is running. Stop it (Ctrl+C in its terminal), then run this again."
  fi
  mkdir -p "$HOME/llama"
  cp -R "$BUNDLE/llama/." "$HOME/llama/"
  # files copied from another computer may be blocked by macOS until this mark is removed
  [ "$(uname -s)" = Darwin ] && xattr -dr com.apple.quarantine "$HOME/llama" 2>/dev/null || true
fi
"$HOME/llama/llama-server" --version >/dev/null 2>&1 || fail "~/llama/llama-server does not run on this computer."
ok "$("$HOME/llama/llama-server" --version 2>&1 | grep -m1 version)"

# ---- 6. the model --------------------------------------------------------------------------------------------
if [ "$HAS_MODEL" = 1 ]; then
  say "Sarvam 30B model (models/)"
  mkdir -p models
  for f in "$BUNDLE"/models/*.gguf; do
    name="$(basename "$f")"
    if [ -s "models/$name" ] && [ "$(stat -f%z "models/$name" 2>/dev/null || stat -c%s "models/$name")" = "$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f")" ]; then
      continue
    fi
    cp -c "$f" "models/$name" 2>/dev/null || cp "$f" "models/$name"
  done
  ok "$(ls models/*.gguf | wc -l | tr -d ' ') model files ($(du -sh models | cut -f1))"
else
  say "Model: skipped (AI_MODE=mock)"
fi

# ---- 6b. Stage 8: language and voice models -------------------------------------------------------------------
if [ "$HAS_LANG" = 1 ]; then
  say "Language and voice models (translation, voices, speech-to-text)"
  mkdir -p models
  cp -cR "$BUNDLE/lang-models/." models/ 2>/dev/null || cp -R "$BUNDLE/lang-models/." models/
  ok "IndicTrans2, Piper voices (Hindi, Telugu, Malayalam, Urdu), IndicConformer (Hindi, Tamil), Whisper small ($(du -sh "$BUNDLE/lang-models" | cut -f1))"
else
  say "Language and voice models: not in the bundle"
  warn "translation goes through the AI model (TRANSLATE_ENGINE=llm, slow); voices only from macOS; no speech-to-text"
fi

# ---- 7. settings (.env) ----------------------------------------------------------------------------------------
say "Settings (.env)"
if [ -f .env ]; then
  ok ".env already exists: kept as it is"
else
  cp .env.example .env
  chmod 600 .env
  if [ "$HAS_MODEL" = 0 ]; then
    sed -i.bak 's/^AI_MODE=local/AI_MODE=mock/' .env && rm -f .env.bak
    ok ".env made from .env.example, with AI_MODE=mock (no model installed)"
  else
    ok ".env made from .env.example (AI_MODE=local). The secret keys are made at the first start."
  fi
  if [ "$HAS_LANG" = 0 ]; then
    if [ "$HAS_MODEL" = 0 ]; then  # nothing to translate with: test engines
      sed -i.bak -e 's/^TRANSLATE_ENGINE=.*/TRANSLATE_ENGINE=mock/' -e 's/^TTS_ENGINE=.*/TTS_ENGINE=mock/' \
        -e 's/^STT_ENGINE=.*/STT_ENGINE=mock/' .env && rm -f .env.bak
      ok "no language models: TRANSLATE_ENGINE, TTS_ENGINE and STT_ENGINE set to mock (test answers)"
    else
      sed -i.bak -e 's/^TRANSLATE_ENGINE=.*/TRANSLATE_ENGINE=llm/' -e 's/^TTS_ENGINE=.*/TTS_ENGINE=say/' .env && rm -f .env.bak
      ok "no language models: TRANSLATE_ENGINE=llm (through the AI model) and TTS_ENGINE=say (macOS voices)"
    fi
  fi
fi

# ---- 8. quick test ---------------------------------------------------------------------------------------------------
if [ "$RUN_TESTS" = 1 ]; then
  say "Quick test (backend tests with the mock AI, about 2 minutes)"
  (cd backend && .venv/bin/python -m pytest -q -x >/tmp/pramaan-install-tests.log 2>&1) \
    || fail "Some tests failed: see /tmp/pramaan-install-tests.log"
  ok "$(tail -1 /tmp/pramaan-install-tests.log)"
fi

printf '\nPramaan AI is installed.\n'
echo "  Start the app:            ./scripts/start.sh          then open http://localhost:5173"
[ "$HAS_MODEL" = 1 ] && echo "  Start the local AI:       ./scripts/start-ai.sh       (in a second terminal; loading takes a few minutes)"
echo "  Public verify page:       ./scripts/serve-verify.sh   (optional, port 8090)"
echo "The first time, the app asks you to create the first Admin account."
