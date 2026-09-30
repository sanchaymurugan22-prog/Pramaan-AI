#!/usr/bin/env bash
# Start the local AI model (Sarvam 30B) with llama.cpp on http://localhost:8081.
# Run this in its own terminal, before or after scripts/start.sh. Press Ctrl+C to stop it.
#
# Flags:
#   -hf ...                 the Sarvam 30B Q4 model (already downloaded to ~/.cache/huggingface)
#   --offline               never go to the internet; use the downloaded copy only
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

exec "$LLAMA_SERVER" -hf sarvamai/sarvam-30b-gguf:Q4_K_M --offline --port 8081 -c 4096 -t 4 -np 1 -b 512 --reasoning-budget 0
