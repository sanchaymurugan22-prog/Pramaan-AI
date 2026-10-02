"""Encryption at rest (Stage 6B): the database and every file under data/jobs/ are encrypted.

One secret, DB_KEY in .env (256 bits, made on first run if empty, never printed or logged). Two keys are
derived from it with HKDF-SHA256, so the database and the files never share a key:
  - the database key: SQLCipher encrypts the whole SQLite file (AES-256, every page)
  - the file key: AES-256-GCM for source files, extracted text and exports

An encrypted file looks like this:
  PRMNENC1 (8 bytes: "this is a Pramaan encrypted file, format 1")
  nonce    (12 random bytes, new for every write)
  ciphertext + 16-byte GCM tag (any change to the file is detected when it is read)

In production the key would not sit in a file next to the data: it would be typed as a passphrase or
read from a hardware token when the app starts (see README, "Encryption at rest").
"""

import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import ensure_secret

log = logging.getLogger("pramaan.crypto")

MAGIC = b"PRMNENC1"
NONCE_BYTES = 12


class DecryptionError(Exception):
    """A file could not be decrypted: wrong DB_KEY, or the file was changed or damaged."""


@lru_cache(maxsize=1)
def _master_key() -> bytes:
    value = ensure_secret("DB_KEY")
    try:
        key = bytes.fromhex(value)
    except ValueError:
        key = b""
    if len(key) != 32:
        # Say what is wrong without showing the value.
        raise RuntimeError("DB_KEY in .env must be 64 hexadecimal characters (256 bits). Leave it empty only on a "
                           "brand-new install: a new key is then made for you. Changing the key of an existing "
                           "install makes the data unreadable.")
    return key


def _derive(purpose: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=f"pramaan-ai {purpose} v1".encode()).derive(_master_key())


@lru_cache(maxsize=1)
def database_key_hex() -> str:
    """The SQLCipher key, as 64 hex characters (used as a raw key: x'...')."""
    return _derive("database").hex()


@lru_cache(maxsize=1)
def _file_cipher() -> AESGCM:
    return AESGCM(_derive("files"))


# ---- bytes -----------------------------------------------------------------------------------------


def is_encrypted(data: bytes) -> bool:
    return data.startswith(MAGIC)


def encrypt(data: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return MAGIC + nonce + _file_cipher().encrypt(nonce, data, MAGIC)


def decrypt(blob: bytes) -> bytes:
    if not is_encrypted(blob):
        raise DecryptionError("This file is not encrypted by Pramaan AI (it may have been replaced).")
    nonce, ciphertext = blob[len(MAGIC):len(MAGIC) + NONCE_BYTES], blob[len(MAGIC) + NONCE_BYTES:]
    try:
        return _file_cipher().decrypt(nonce, ciphertext, MAGIC)
    except Exception as exc:  # cryptography raises InvalidTag
        raise DecryptionError("This file cannot be decrypted: the key is wrong, or the file was changed.") from exc


# ---- files ------------------------------------------------------------------------------------------


def write_file(path: Path, data: bytes) -> Path:
    """Encrypt and save. Written to a temporary name first, so a half-written file is never read. The
    temporary name is unique, so two downloads saving the same file at the same moment do not collide."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=path.parent)  # mode 0600
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(encrypt(data))
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def read_file(path: Path | str) -> bytes:
    return decrypt(Path(path).read_bytes())


def encrypt_existing_files(folder: Path) -> int:
    """Encrypt, in place, every file under `folder` that is not encrypted yet (files saved before
    Stage 6B). Safe to run on every start: encrypted files are skipped. Returns how many were done."""
    done = 0
    if not folder.exists():
        return 0
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        if path.name.endswith(".part"):  # a write that never finished
            path.unlink()
            continue
        with path.open("rb") as file:
            if file.read(len(MAGIC)) == MAGIC:
                continue
        plain = path.read_bytes()
        write_file(path, plain)
        if read_file(path) != plain:  # never lose data: check before moving on
            raise RuntimeError(f"Encrypting {path} did not round-trip; stopped.")
        done += 1
    if done:
        log.warning("Encrypted %d stored file(s) under %s that were saved before encryption was added", done, folder)
    return done
