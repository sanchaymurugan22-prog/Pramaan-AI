# Pramaan AI (प्रमाण) — User Guide

Welcome to **Pramaan AI**, the offline-first automated content transformation and verification platform.

---

## 🚀 Getting Started

### 1. Installation
- **macOS**: Double-click `Pramaan AI-1.0.0.dmg` and drag **Pramaan AI** into your Applications folder.
- **Windows**: Run `Pramaan AI Setup 1.0.0.exe` and follow the setup wizard.
- **Linux**: Make `Pramaan AI-1.0.0.AppImage` executable (`chmod +x`) and run.

### 2. First Launch & Offline Setup
1. Launch Pramaan AI from your Applications menu or Desktop shortcut.
2. The initial launch wizard checks system RAM (16 GB required), CPU cores, and free disk space (25 GB required).
3. Download the offline AI models during first setup (requires internet once).
4. After setup completes, turn **Wi-Fi OFF** — all AI generation, fact extraction, and document signing runs 100% offline.

---

## 📄 Key Features & Workflows

### 📥 1. Ingestion & Safety Scan
- Upload source documents (PDF, Word DOCX, TXT, images, or audio/video).
- The automatic safety scanner checks for PII (Aadhaar, PAN, phone numbers, IP addresses, credentials) and assigns a TLP classification (**RED**, **AMBER**, **GREEN**, **CLEAR**).

### 🔍 2. Fact Sheet Extraction
- The offline Sarvam 30B model extracts a structured Fact Sheet mapping every key fact, date, entity, and quote back to exact page numbers in the source.

### 📑 3. Document Generation
Generate 7 verified output formats from the single Fact Sheet:
1. **CERT-In Style Advisory**
2. **Executive Summary**
3. **Presentation Deck** (+ Speaker Notes)
4. **Video Package** (Script, Storyboard, Subtitles)
5. **Infographic Layout**
6. **LinkedIn Post**
7. **X (Twitter) Thread**

### ✍️ 4. Review, Digital Signing & QR Verification
- Reviewers approve outputs with sentence-by-sentence source tracing.
- Signed documents receive a cryptographic SHA-256 hash-chain entry and embedded QR code for tamper-evident verification.

---

## 🔒 Offline & Security Rules
- **No Internet Required**: Data never leaves your organization's physical machine.
- **Role Access**: Admin, Operator, Reviewer access controls.
