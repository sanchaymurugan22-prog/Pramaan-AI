# Pramaan AI — Troubleshooting Guide

Common issues, error codes, and diagnostic steps for Pramaan AI Desktop.

---

## 🚨 Common Diagnostic Issues & Solutions

### 1. `Cannot find module 'dotenv'` or Missing Module Error
- **Cause**: Dependency listed in `devDependencies` instead of `dependencies` in `package.json`.
- **Fix**: Run `npm install dotenv --save-prod` inside `desktop/` and rebuild with `npm run pack`.

### 2. `SIGILL` (Signal 4: Illegal Instruction) Crash on Intel Mac
- **Cause**: Incompatibility with experimental Electron v44 binaries on 2017 Intel Core i7 hardware.
- **Fix**: Pinned to stable `electron@32.2.0` in `desktop/package.json`.

### 3. Port 8000 or 5173 Address Already in Use (`EADDRINUSE`)
- **Cause**: An earlier copy of Pramaan AI or Uvicorn/Vite process was left running.
- **Fix**: The launcher automatically detects open ports and reuses existing services safely. To force stop:
  ```bash
  lsof -i :8000 -i :5173 -i :8081
  kill -9 <PID>
  ```

### 4. Sarvam 30B Model Not Loaded (`Port 8081 Connection Refused`)
- **Cause**: GGUF model files missing from `models/` directory or Hugging Face cache.
- **Fix**: Run the First-Run Setup Wizard inside the application or execute `backend/.venv/bin/python scripts/download-models.py`.

### 5. Out of Memory / Slow Inference
- **Cause**: Sarvam 30B GGUF model requires ~18-20 GB memory context.
- **Fix**: Ensure virtual memory/swap space is enabled. Keep prompt context configured to `-c 4096` and thread count to `-t 4`.

---

## 🪵 Accessing Logs

- **macOS Logs**: `~/Library/Logs/Pramaan AI/`
- **Windows Logs**: `%APPDATA%\Pramaan AI\logs\`
- **Linux Logs**: `~/.config/pramaan-ai/logs/`
