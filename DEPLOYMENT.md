# Pramaan AI (प्रमाण) — Production Deployment Guide

This document specifies the production deployment architecture, model management, runtime packaging, signing, CI/CD workflows, and release procedures for Pramaan AI Desktop.

---

## 🏛️ Architecture Overview

Pramaan AI is an offline-first desktop application designed for secure environments.

```
┌─────────────────────────────────────────────────────────┐
│                     Electron Shell                      │
│            (Desktop App Container / Preload IPC)        │
└───────────┬─────────────────┬─────────────────┬─────────┘
            │                 │                 │
            ▼                 ▼                 ▼
   ┌────────────────┐┌────────────────┐┌────────────────┐
   │ Production UI  ││ FastAPI Backend││  llama-server  │
   │  React Static  ││ Python Service ││  Sarvam 30B    │
   │  (Port 5173)   ││  (Port 8000)   ││  (Port 8081)   │
   └────────────────┘└────────────────┘└────────────────┘
```

- **Electron**: Manages app lifecycle, first-run wizard, and IPC bridges.
- **Frontend**: Vite-built React static app served via local HTTP with `/api` reverse proxying.
- **Backend**: FastAPI Python backend handling ingestion, TLP safety, fact sheet extraction, document generation, hash-chained signing, and verification.
- **AI Engine**: `llama-server` running Sarvam 30B GGUF (`Q4_K_M`) at 4096 context length.

---

## 📦 Runtime & Binary Packaging

### 1. Platform Executable Resolution
Per-platform binary executables are placed in `Contents/Resources/bin/`:
- **macOS**: `pramaan-backend-darwin-x64`, `pramaan-backend-darwin-arm64`
- **Windows**: `pramaan-backend-win32-x64.exe`
- **Linux**: `pramaan-backend-linux-x64`

### 2. LLM Engine Binaries
- **macOS**: `llama-server-darwin-x64`, `llama-server-darwin-arm64`
- **Windows**: `llama-server-win32-x64.exe`
- **Linux**: `llama-server-linux-x64`

---

## 🤖 Offline AI Model Storage

Large models are stored outside `app.asar` in the OS application data directory (`app.getPath('userData')`):

- **macOS**: `~/Library/Application Support/Pramaan AI/models/`
- **Windows**: `%APPDATA%\Pramaan AI\models\`
- **Linux**: `~/.config/pramaan-ai/models/`

### Downloaded Assets & SHA-256 Hashes
- **Sarvam 30B Q4_K_M GGUF**: `sarvam-30b-Q4_K_M.gguf-00001-of-00006.gguf` (~20 GB)
- **AI4Bharat IndicTrans2**: `indictrans2-en-indic-ct2-int8/` (~1.1 GB)
- **Sherpa-ONNX Voice Models**: Piper int8 voices for Hindi, Malayalam, Urdu, Telugu (~150 MB)
- **STT Models**: IndicConformer uint8 & Whisper small uint8 (~500 MB)

---

## 🔒 Security Specifications

1. **Local Host Binding**: All internal HTTP services bind exclusively to `127.0.0.1`.
2. **IPC Isolation**: `contextIsolation: true` and `nodeIntegration: false` enforced.
3. **Local Encryption**: Database encrypted using SQLCipher / AES-256 (`DB_KEY` stored in `.env`).
4. **Digital Signatures**: HMAC SHA-256 document hashing and QR verification.

---

## 🛠️ CI/CD & Build Commands

Release binaries are built via GitHub Actions (`.github/workflows/build-desktop.yml`).

To build locally:

```bash
cd desktop

# macOS DMG
npm run dist:mac

# Windows Setup.exe
npm run dist:win

# Linux AppImage / .deb
npm run dist:linux
```
