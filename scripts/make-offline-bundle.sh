#!/usr/bin/env bash
# Make the OFFLINE BUNDLE: one folder with everything scripts/install.sh needs, so Pramaan AI can be
# installed on a computer with no internet. Run this on a computer WITH internet, of the same kind as
# the target (same operating system and processor: Python wheels and llama.cpp are built per platform).
#
#   ./scripts/make-offline-bundle.sh                 bundle in ./offline-bundle (about 19 GB with the model)
#   ./scripts/make-offline-bundle.sh /Volumes/USB/pramaan-bundle
#   ./scripts/make-offline-bundle.sh --no-model      without the 18 GB model (enough for AI_MODE=mock)
#
# What goes in:
#   python/wheels/   every Python package of backend/requirements.txt, as ready-made wheels
#   node/npm-cache/  every npm package of frontend/package-lock.json (npm's own cache format)
#   llama/           the llama.cpp binaries (copied from ~/llama, or downloaded: LLAMA_URL=...)
#   models/          Sarvam 30B Q4_K_M, 6 GGUF files (from the Hugging Face cache, or downloaded)
#   MANIFEST.txt     what is in it and for which platform;  SHA256SUMS  a fingerprint of every file
# Python 3.12 and Node are NOT included: install them from their own offline installers
# (python.org .pkg, nodejs.org .pkg) and put those next to the bundle if the target has neither.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL_REPO="sarvamai/sarvam-30b-gguf"
MODEL_FILES=()
for n in 1 2 3 4 5 6; do MODEL_FILES+=("sarvam-30b-Q4_K_M.gguf-0000$n-of-00006.gguf"); done
WITH_MODEL=1
BUNDLE="$ROOT/offline-bundle"
for arg in "$@"; do
  case "$arg" in
    --no-model) WITH_MODEL=0 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $arg (see --help)"; exit 1 ;;
    *) BUNDLE="$arg" ;;
  esac
done

say() { printf '\n== %s\n' "$*"; }
fail() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

# ---- checks ---------------------------------------------------------------------------------------
say "Checking this computer"
PYTHON=""
for candidate in backend/.venv/bin/python python3.12; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
    PYTHON="$candidate"; break
  fi
done
[ -n "$PYTHON" ] || fail "Python 3.12 is needed (python.org). It must be the same version as on the target computer."
command -v npm >/dev/null 2>&1 || fail "npm is needed (install Node LTS from nodejs.org)."
curl -s -m 10 -o /dev/null https://pypi.org/simple/ || fail "No internet: this script downloads packages. Run it on a computer that is online."

PLATFORM="$(uname -s)-$(uname -m)"
NEEDED_GB=2
[ "$WITH_MODEL" = 1 ] && NEEDED_GB=22
mkdir -p "$BUNDLE"
FREE_GB=$(df -Pk "$BUNDLE" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
[ "$FREE_GB" -ge "$NEEDED_GB" ] || fail "Not enough free disk space at $BUNDLE: $FREE_GB GB free, $NEEDED_GB GB needed."
echo "Platform $PLATFORM · Python $("$PYTHON" -V 2>&1 | cut -d' ' -f2) · npm $(npm -v) · $FREE_GB GB free · bundle: $BUNDLE"

# ---- Python wheels ----------------------------------------------------------------------------------
say "Python packages (wheels)"
mkdir -p "$BUNDLE/python/wheels"
"$PYTHON" -m pip download --quiet --only-binary=:all: --dest "$BUNDLE/python/wheels" -r backend/requirements.txt \
  || fail "pip could not download every package as a ready-made wheel for $PLATFORM."
echo "$(ls "$BUNDLE/python/wheels" | wc -l | tr -d ' ') wheels"

# ---- npm packages ------------------------------------------------------------------------------------
say "Frontend packages (npm cache)"
WORK="$(mktemp -d)"
cp frontend/package.json frontend/package-lock.json "$WORK/"
(cd "$WORK" && npm ci --cache "$BUNDLE/node/npm-cache" --no-audit --no-fund --no-update-notifier --loglevel=error >/dev/null) \
  || fail "npm could not download the frontend packages."
rm -rf "$WORK"
cp frontend/package-lock.json "$BUNDLE/node/package-lock.json"  # to check that the bundle matches the code
echo "npm cache: $(du -sh "$BUNDLE/node/npm-cache" | cut -f1)"

# ---- llama.cpp -----------------------------------------------------------------------------------------
say "llama.cpp (llama-server)"
mkdir -p "$BUNDLE/llama"
if [ -n "${LLAMA_URL:-}" ]; then
  echo "Downloading $LLAMA_URL"
  curl -fL --progress-bar -o "$BUNDLE/llama/llama.zip" "$LLAMA_URL" || fail "Could not download llama.cpp from LLAMA_URL."
  (cd "$BUNDLE/llama" && unzip -q -o llama.zip && rm llama.zip)
  # release zips keep the binaries in build/bin/: move them up
  if [ -d "$BUNDLE/llama/build/bin" ]; then mv "$BUNDLE/llama/build/bin/"* "$BUNDLE/llama/" && rm -rf "$BUNDLE/llama/build"; fi
elif [ -x "$HOME/llama/llama-server" ]; then
  cp -R "$HOME/llama/." "$BUNDLE/llama/"
else
  fail "No llama.cpp found. Put the prebuilt binaries in ~/llama, or set LLAMA_URL to a release zip from
         https://github.com/ggml-org/llama.cpp/releases (for an Intel Mac: llama-<build>-bin-macos-x64.zip)."
fi
[ -x "$BUNDLE/llama/llama-server" ] || fail "llama-server is missing from $BUNDLE/llama."
"$BUNDLE/llama/llama-server" --version 2>&1 | grep -m1 version || true

# ---- the model -----------------------------------------------------------------------------------------
if [ "$WITH_MODEL" = 1 ]; then
  say "Sarvam 30B model (6 files, about 18 GB)"
  mkdir -p "$BUNDLE/models"
  CACHE="$HOME/.cache/huggingface/hub/models--sarvamai--sarvam-30b-gguf/snapshots"
  for f in "${MODEL_FILES[@]}"; do
    if [ -s "$BUNDLE/models/$f" ]; then echo "already there: $f"; continue; fi
    found="$(ls "$CACHE"/*/"$f" 2>/dev/null | head -1 || true)"
    if [ -n "$found" ]; then
      # cp -c makes an instant copy-on-write clone on APFS (no extra space); plain copy elsewhere
      cp -cL "$found" "$BUNDLE/models/$f" 2>/dev/null || cp -L "$found" "$BUNDLE/models/$f"
      echo "copied from the Hugging Face cache: $f"
    else
      echo "downloading $f"
      curl -fL --progress-bar -C - -o "$BUNDLE/models/$f.part" "https://huggingface.co/$MODEL_REPO/resolve/main/$f" \
        || fail "Could not download $f."
      mv "$BUNDLE/models/$f.part" "$BUNDLE/models/$f"
    fi
  done
else
  rm -rf "$BUNDLE/models"
fi

# ---- manifest and fingerprints --------------------------------------------------------------------------
say "Fingerprints"
{
  echo "Pramaan AI offline bundle"
  echo "made: $(date '+%Y-%m-%d %H:%M %Z') on $(hostname -s)"
  echo "platform: $PLATFORM"
  echo "python: $("$PYTHON" -V 2>&1 | cut -d' ' -f2)"
  echo "node: $(node -v)"
  echo "code: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "model: $([ "$WITH_MODEL" = 1 ] && echo "$MODEL_REPO Q4_K_M" || echo "not included (AI_MODE=mock only)")"
} > "$BUNDLE/MANIFEST.txt"
(cd "$BUNDLE" && find . -type f ! -name SHA256SUMS ! -name MANIFEST.txt -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS)
echo "$(wc -l < "$BUNDLE/SHA256SUMS" | tr -d ' ') files fingerprinted"

say "Done"
cat "$BUNDLE/MANIFEST.txt"
echo "Size: $(du -sh "$BUNDLE" | cut -f1)"
echo
echo "Copy $BUNDLE and this project folder to the offline computer, then run there:"
echo "  ./scripts/install.sh $(basename "$BUNDLE")"
