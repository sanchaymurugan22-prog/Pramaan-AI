# Pramaan AI — Developer Build Guide

This guide details setting up the local development environment, running tests, and building release installers for macOS, Windows, and Linux.

---

## 💻 Prerequisites

- **Node.js**: v22 LTS
- **Python**: v3.12+
- **Git**: Xcode CLT (macOS) or Git for Windows
- **llama.cpp**: Prebuilt binaries placed in `~/llama/` or PATH

---

## 🛠️ Local Development Setup

```bash
# Clone project and enter root directory
cd ~/Documents/"Pramaan AI"

# 1. Setup Backend Virtualenv
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 2. Setup Frontend Dependencies
cd frontend
npm install
npm run build
cd ..

# 3. Setup Desktop Electron App
cd desktop
npm install
npm start
```

---

## 📦 Packaging Standalone Installers

To package standalone installers:

```bash
cd desktop

# macOS Universal DMG (Intel + Apple Silicon)
npm run dist:mac

# Windows NSIS Setup.exe
npm run dist:win

# Linux AppImage
npm run dist:linux
```

All build artifacts are written to `desktop/dist/`.

---

## 🤖 Model Management Scripts

```bash
# Download STT, TTS, and IndicTrans2 translation models
backend/.venv/bin/python scripts/download-models.py

# Download Sarvam 30B GGUF model via Hugging Face CLI
huggingface-cli download sarvamai/sarvam-30b-gguf sarvam-30b-Q4_K_M.gguf
```
