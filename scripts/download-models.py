"""Download the Stage 8 language and voice models into models/ (needs internet once; then everything is offline).

    backend/.venv/bin/python scripts/download-models.py              # everything (about 2.6 GB, in parts of at most 1.1 GB)
    backend/.venv/bin/python scripts/download-models.py --only stt   # translate | tts | stt (comma-separated)
    backend/.venv/bin/python scripts/download-models.py --dest /Volumes/USB/bundle/models

What it fetches (sizes are the downloads):
  translate  AI4Bharat IndicTrans2 en->indic distilled 200M (1.1 GB, MIT). The model page asks for access
             once: click "Agree" on huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M and put HF_TOKEN
             in .env. It is then converted to CTranslate2 8-bit (about 0.3 GB) by
             scripts/convert-indictrans2.py, which this script runs at the end.
  tts        Piper voices for sherpa-onnx (8-bit, about 21 MB each): Hindi, Malayalam, Urdu ready-made;
             Telugu converted here (scripts/convert-piper-voice.py).
  stt        AI4Bharat IndicConformer for Hindi and Tamil (481 MB each at full precision, quantised here to
             8 bits, about 150 MB each) and Whisper small 8-bit for English (about 250 MB).

Every large file is checked against the SHA-256 published by Hugging Face. Files already downloaded are
kept (a half-finished download resumes). HF_TOKEN is read from .env and never printed.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
HF = "https://huggingface.co"
GITHUB_TTS = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"

# --- what to download ---------------------------------------------------------------------------------

INDICTRANS2 = "ai4bharat/indictrans2-en-indic-dist-200M"
INDICTRANS2_FILES = ["config.json", "dict.SRC.json", "dict.TGT.json", "model.SRC", "model.TGT", "model.safetensors",
                     "LICENSE", "README.md"]

# Ready-made sherpa-onnx packages (Piper voices, 8-bit): folder name -> archive
VOICE_PACKAGES = {
    "vits-piper-hi_IN-priyamvada-medium-int8": "vits-piper-hi_IN-priyamvada-medium-int8.tar.bz2",
    "vits-piper-ml_IN-meera-medium-int8": "vits-piper-ml_IN-meera-medium-int8.tar.bz2",
    "vits-piper-ur_PK-fasih-medium-int8": "vits-piper-ur_PK-fasih-medium-int8.tar.bz2",
}
# Piper voices that sherpa-onnx does not package yet: converted here (path in rhasspy/piper-voices)
VOICES_TO_CONVERT = {
    "vits-piper-te_IN-padmavathi-medium-int8": "te/te_IN/padmavathi/medium/te_IN-padmavathi-medium",
}

# Speech-to-text. onnxruntime's CPU backend has no 8-bit convolution with SIGNED weights (ConvInteger int8),
# so the ready-made "int8" files cannot run on a CPU. Whisper comes as "uint8" (works); IndicConformer is
# downloaded at full precision once and quantised here to uint8 (scripts/quantize-onnx.py), as sherpa-onnx does.
STT_MODELS = {
    # folder: (repo, files to keep, full-precision files to quantise or None)
    "indicconformer-hi": ("OpenVoiceOS/ai4bharat-indicconformer-hi-onnx", ["config.json", "vocab.txt", "README.md"],
                          ["model.onnx", "model.onnx_data"]),
    "indicconformer-ta": ("OpenVoiceOS/ai4bharat-indicconformer-ta-onnx", ["config.json", "vocab.txt", "README.md"],
                          ["model.onnx", "model.onnx_data"]),
    "whisper-small": ("onnx-community/whisper-small", [
        "config.json", "generation_config.json", "preprocessor_config.json", "added_tokens.json", "vocab.json",
        "merges.txt", "normalizer.json", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
        "onnx/encoder_model_uint8.onnx", "onnx/decoder_model_merged_uint8.onnx",
    ], None),
}


def say(text: str) -> None:
    print(text, flush=True)


def hf_headers(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def hf_listing(client: httpx.Client, repo: str, token: str | None) -> dict[str, dict]:
    """File name -> {size, sha256 (large files only)} from the Hugging Face API."""
    r = client.get(f"{HF}/api/models/{repo}", params={"blobs": "true"}, headers=hf_headers(token))
    if r.status_code in (401, 403):
        sys.exit(f"No access to {repo}. Open {HF}/{repo}, click 'Agree', and put HF_TOKEN=... in .env.")
    r.raise_for_status()
    return {s["rfilename"]: {"size": s.get("size"), "sha256": (s.get("lfs") or {}).get("sha256")}
            for s in r.json().get("siblings", [])}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(client: httpx.Client, url: str, dest: Path, headers: dict | None = None,
          size: int | None = None, sha256: str | None = None) -> None:
    """Download url to dest, resuming a .part file; check size and SHA-256 when known."""
    if dest.exists() and (size is None or dest.stat().st_size == size):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    h = dict(headers or {})
    if have:
        h["Range"] = f"bytes={have}-"
    with client.stream("GET", url, headers=h, follow_redirects=True) as r:
        if r.status_code == 416:  # already complete
            pass
        elif r.status_code not in (200, 206):
            sys.exit(f"Download failed ({r.status_code}): {url.split('?')[0]}")
        else:
            mode = "ab" if r.status_code == 206 else "wb"
            total = int(r.headers.get("content-length", 0)) + (have if mode == "ab" else 0)
            done, step = (have if mode == "ab" else 0), 0
            with part.open(mode) as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total > 50e6 and done * 10 // total > step:
                        step = done * 10 // total
                        say(f"      {dest.name}: {done / 1e6:,.0f} of {total / 1e6:,.0f} MB")
    if size is not None and part.stat().st_size != size:
        sys.exit(f"{dest.name}: size {part.stat().st_size} is not {size}. Run again to resume.")
    if sha256 and sha256_of(part) != sha256:
        part.unlink()
        sys.exit(f"{dest.name}: the SHA-256 does not match. The file was deleted; run again.")
    part.rename(dest)


def get_hf_files(client: httpx.Client, repo: str, files: list[str], dest: Path, token: str | None = None) -> None:
    listing = hf_listing(client, repo, token)
    for name in files:
        if name not in listing:
            sys.exit(f"{repo} has no file {name} any more. Update scripts/download-models.py.")
        info = listing[name]
        fetch(client, f"{HF}/{repo}/resolve/main/{name}", dest / name, hf_headers(token), info["size"], info["sha256"])
    say(f"    OK   {repo} -> {dest.relative_to(dest.parents[1]) if len(dest.parents) > 1 else dest}")


# --- the three groups -----------------------------------------------------------------------------------

def translate(client: httpx.Client, models: Path, token: str | None) -> None:
    say("\n[translate] IndicTrans2 en->indic distilled 200M (AI4Bharat, MIT)")
    if not token:
        sys.exit("HF_TOKEN is missing in .env (the IndicTrans2 page needs one click on 'Agree' first).")
    source = models / "src" / "indictrans2-en-indic-dist-200M"
    get_hf_files(client, INDICTRANS2, INDICTRANS2_FILES, source, token)
    target = models / "indictrans2-en-indic-ct2"
    if (target / "model.bin").exists():
        say("    OK   already converted to CTranslate2")
        return
    say("    converting to CTranslate2 8-bit (about 2 minutes)...")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "convert-indictrans2.py"), str(source), str(target)], check=True)


def tts(client: httpx.Client, models: Path) -> None:
    say("\n[tts] Piper voices for sherpa-onnx (8-bit)")
    voices = models / "tts"
    for folder, archive in VOICE_PACKAGES.items():
        if (voices / folder / "tokens.txt").exists():
            say(f"    OK   {folder} (already here)")
            continue
        tar = voices / archive
        fetch(client, f"{GITHUB_TTS}/{archive}", tar)
        with tarfile.open(tar) as t:
            t.extractall(voices, filter="data")
        tar.unlink()
        say(f"    OK   {folder}")
    espeak = next((voices / f / "espeak-ng-data" for f in VOICE_PACKAGES if (voices / f / "espeak-ng-data").is_dir()), None)
    for folder, path in VOICES_TO_CONVERT.items():
        out = voices / folder
        if (out / "tokens.txt").exists():
            say(f"    OK   {folder} (already here)")
            continue
        raw = models / "src" / "piper" / Path(path).name
        listing = hf_listing(client, "rhasspy/piper-voices", None)
        for suffix in (".onnx", ".onnx.json"):
            info = listing[path + suffix]
            fetch(client, f"{HF}/rhasspy/piper-voices/resolve/main/{path}{suffix}", Path(str(raw) + suffix),
                  None, info["size"], info["sha256"])
        fetch(client, f"{HF}/rhasspy/piper-voices/resolve/main/{Path(path).parent}/MODEL_CARD", raw.parent / (raw.name + ".MODEL_CARD"))
        subprocess.run([sys.executable, str(ROOT / "scripts" / "convert-piper-voice.py"), str(raw) + ".onnx", str(out)], check=True)
        if espeak and not (out / "espeak-ng-data").exists():
            shutil.copytree(espeak, out / "espeak-ng-data")  # the same espeak-ng data for every Piper voice
        shutil.copy(raw.parent / (raw.name + ".MODEL_CARD"), out / "MODEL_CARD")
        say(f"    OK   {folder} (converted)")


def stt(client: httpx.Client, models: Path) -> None:
    say("\n[stt] IndicConformer (AI4Bharat, MIT) for Hindi and Tamil; Whisper small for English")
    for folder, (repo, files, full) in STT_MODELS.items():
        out = models / "stt" / folder
        get_hf_files(client, repo, files, out)
        if full and not (out / "model.uint8.onnx").exists():
            source = models / "src" / folder
            get_hf_files(client, repo, full, source)
            say(f"    quantising {folder} to 8 bits (about a minute)...")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "quantize-onnx.py"), str(source / "model.onnx"),
                            str(out / "model.uint8.onnx")], check=True)
        for old in [*out.glob("*.int8.onnx"), *out.glob("**/*_int8.onnx")]:  # ready-made files a CPU cannot run
            old.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the Stage 8 models (translation, voices, speech-to-text).")
    parser.add_argument("--only", default="translate,tts,stt", help="comma-separated: translate, tts, stt")
    parser.add_argument("--dest", default=str(ROOT / "models"), help="the models folder (default: models/)")
    args = parser.parse_args()
    models = Path(args.dest).resolve()
    token = dotenv_values(ROOT / ".env").get("HF_TOKEN") or None
    groups = [g.strip() for g in args.only.split(",") if g.strip()]
    with httpx.Client(timeout=httpx.Timeout(60, read=300)) as client:
        if "translate" in groups:
            translate(client, models, token)
        if "tts" in groups:
            tts(client, models)
        if "stt" in groups:
            stt(client, models)
    say(f"\nDone. Models are in {models}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
