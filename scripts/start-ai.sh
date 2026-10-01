#!/usr/bin/env bash
# Start the local AI model (Sarvam 30B) with llama.cpp on http://localhost:8081.
# Run this in its own terminal, before or after scripts/start.sh. Press Ctrl+C to stop it.
#
# Flags:
#   -m models/...           the Sarvam 30B Q4 model files put in models/ by scripts/install.sh, or else
#   -hf ... --offline       the copy downloaded earlier to ~/.cache/huggingface (never the internet)
#   --port 8081             the address the backend expects (LLM_BASE_URL in .env)
#   -c 4096                 small context, to fit in 16 GB RAM
#   -t 4                    4 CPU threads
#   -np 1                   one request at a time (saves memory)
#   -b 512                  read the prompt in pieces of 512 tokens, so the server can report
#                           progress (and the backend doesn't time out) while it reads a long prompt
#   --reasoning-budget 0    turn off "thinking", so answers start straight away

set -euo pipefail

# Use llama-server from the PATH if it is there, otherwise the prebuilt copy in ~/llama.
if command -v llama-server >/dev/null 2>&1; then
  LLAMA_SERVER="llama-server"
elif [ -x "$HOME/llama/llama-server" ]; then
  LLAMA_SERVER="$HOME/llama/llama-server"
else
  echo "Could not find llama-server. Put the llama.cpp binaries in ~/llama (see README.md)."
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_FILE="$ROOT/models/sarvam-30b-Q4_K_M.gguf-00001-of-00006.gguf"  # llama.cpp finds parts 2-6 itself
if [ -f "$MODEL_FILE" ]; then
  MODEL=(-m "$MODEL_FILE")
elif [ -d "$HOME/.cache/huggingface/hub/models--sarvamai--sarvam-30b-gguf" ]; then
  MODEL=(-hf sarvamai/sarvam-30b-gguf:Q4_K_M --offline)
else
  echo "The Sarvam 30B model is not installed. Run ./scripts/install.sh with a bundle that has the model,"
  echo "or use AI_MODE=mock in .env (no model needed)."
  exit 1
fi

# Port 8081 must be free (an AI server from earlier may still be running)
if lsof -nP -t -iTCP:8081 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8081 is already in use (process $(lsof -nP -t -iTCP:8081 -sTCP:LISTEN | head -1))."
  echo "If it is an earlier llama-server, it is already running: use it, or stop it first (Ctrl+C in its terminal)."
  exit 1
fi

echo "Loading Sarvam 30B (this takes a few minutes; wait for \"server is listening\")..."
exec "$LLAMA_SERVER" "${MODEL[@]}" --port 8081 -c 4096 -t 4 -np 1 -b 512 --reasoning-budget 0
