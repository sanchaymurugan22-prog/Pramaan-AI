"""Who signs: one interface, two backends (SIGNER in .env).

    TestSigner  SIGNER=test (default). An ECDSA P-256 key made on this computer the first time it is
                needed. The private key is stored ENCRYPTED with the Stage 6B file key
                (data/keys/test-signer.key, AES-256-GCM, see app/crypto.py) and is never printed or logged.
                The public key (data/keys/test-signer.pub.pem) is published with the verify page.
                Good for development and the demo; it is not a legal digital signature.

    DscSigner   SIGNER=dsc. A Class 3 DSC on a USB token, through the token maker's PKCS#11 library
                (PyKCS11). DESIGN ONLY - NOT TESTED: no token was available while building it. See the
                class for what is missing.

Signatures are ECDSA with SHA-256, in the "raw" form r||s (64 bytes for P-256, base64). That is the
form the browser's Web Crypto API expects, so the public verify page can check them with no library.
"""

import base64
import hashlib
import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

from app import crypto
from app.config import settings

log = logging.getLogger("pramaan.signing")

ALGORITHM = "ECDSA-P256-SHA256"


class SigningError(Exception):
    """Signing is not possible (no key, wrong PIN, token missing ...). The message is shown to the reviewer."""


class Signer:
    """What every signer can do."""

    kind = "base"
    label = ""          # shown in the sign dialog, e.g. "Test key (ECDSA P-256)"
    certificate_class = ""

    def public_key_pem(self) -> str:
        raise NotImplementedError

    def sign(self, data: bytes) -> str:
        """Signature of `data` as base64 of raw r||s."""
        raise NotImplementedError

    def key_id(self) -> str:
        """Short fingerprint of the public key: the first 16 hex characters of SHA-256 of its DER form."""
        return key_id(self.public_key_pem())

    def describe(self) -> dict:
        return {"kind": self.kind, "label": self.label, "certificate_class": self.certificate_class,
                "algorithm": ALGORITHM, "key_id": self.key_id()}


class TestSigner(Signer):
    __test__ = False  # not a pytest test class, despite the name
    kind = "test"
    label = "Test key on this computer (ECDSA P-256)"
    certificate_class = "Test key (not a legal DSC)"

    def __init__(self, folder: Path | None = None):
        self.folder = folder or settings.data_dir / "keys"

    @property
    def _private_path(self) -> Path:
        return self.folder / "test-signer.key"

    @property
    def _public_path(self) -> Path:
        return self.folder / "test-signer.pub.pem"

    def _private_key(self) -> ec.EllipticCurvePrivateKey:
        if not self._private_path.exists():
            self._make_key()
        pem = crypto.read_file(self._private_path)  # stored encrypted
        return serialization.load_pem_private_key(pem, password=None)

    def _make_key(self) -> None:
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        crypto.write_file(self._private_path, pem)
        public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
        self._public_path.write_bytes(public)
        os.chmod(self._private_path, 0o600)
        log.warning("Made a new test signing key (the private key is stored encrypted in %s)", self.folder)

    def public_key_pem(self) -> str:
        if not self._public_path.exists():
            self._make_key()
        return self._public_path.read_text()

    def sign(self, data: bytes) -> str:
        der = self._private_key().sign(data, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode()


class DscSigner(Signer):
    """A Class 3 DSC on a USB token (ePass / ProxKey / Watchdata ...), through PKCS#11.

    *** DESIGN ONLY - NOT TESTED. No token was available while this was written. ***

    How it would work:
      1. PKCS11_LIB in .env = the token maker's library (e.g. /usr/local/lib/libcastle.1.0.0.dylib).
      2. The reviewer types the token PIN in the sign dialog; it is passed here, used once, never stored.
      3. Find the private key whose label is DSC_KEY_LABEL; sign with CKM_ECDSA_SHA256 (EC keys) or
         CKM_SHA256_RSA_PKCS (RSA keys).
    What is missing before real use:
      - Most Indian Class 3 DSCs are RSA-2048, not EC. The verify page then needs RSASSA-PKCS1-v1_5
        (Web Crypto supports it), and records must say which algorithm was used ("algorithm" is
        already in every record for this reason).
      - The certificate chain (CCA India root -> licensed CA -> person) should be checked and published,
        and the signer's certificate put in each record.
      - Error handling for a missing token, a locked PIN, and an expired certificate.
    """

    kind = "dsc"
    label = "Class 3 DSC on a USB token (PKCS#11) - NOT TESTED"
    certificate_class = "Class 3 (signing)"

    def __init__(self, pin: str = ""):
        self.pin = pin

    def _session(self):
        try:
            import PyKCS11  # optional: pip install PyKCS11 (only for SIGNER=dsc)
        except ImportError as exc:
            raise SigningError("DSC signing needs the PyKCS11 package (pip install PyKCS11).") from exc
        if not settings.pkcs11_lib:
            raise SigningError("Set PKCS11_LIB in .env to your token's PKCS#11 library.")
        library = PyKCS11.PyKCS11Lib()
        library.load(settings.pkcs11_lib)
        slots = library.getSlotList(tokenPresent=True)
        if not slots:
            raise SigningError("No DSC token found. Plug it in and try again.")
        session = library.openSession(slots[0], PyKCS11.CKF_SERIAL_SESSION)
        if self.pin:
            session.login(self.pin)
        return PyKCS11, session

    def _find(self, PyKCS11, session, cls):
        template = [(PyKCS11.CKA_CLASS, cls)]
        if settings.dsc_key_label:
            template.append((PyKCS11.CKA_LABEL, settings.dsc_key_label))
        found = session.findObjects(template)
        if not found:
            raise SigningError("The signing key was not found on the token (check DSC_KEY_LABEL).")
        return found[0]

    def public_key_pem(self) -> str:
        raise SigningError("Reading the public key from a DSC token is not built yet (design only, not tested).")

    def sign(self, data: bytes) -> str:
        PyKCS11, session = self._session()
        try:
            key = self._find(PyKCS11, session, PyKCS11.CKO_PRIVATE_KEY)
            raw = bytes(session.sign(key, data, PyKCS11.Mechanism(PyKCS11.CKM_ECDSA_SHA256, None)))
            return base64.b64encode(raw).decode()  # PKCS#11 ECDSA signatures are already raw r||s
        finally:
            session.logout()
            session.closeSession()


def get_signer(pin: str = "") -> Signer:
    if settings.signer == "dsc":
        return DscSigner(pin)
    return _test_signer()


@lru_cache(maxsize=1)
def _test_signer() -> TestSigner:
    return TestSigner()


# ---- checking -----------------------------------------------------------------------------------


def key_id(public_pem: str) -> str:
    der = serialization.load_pem_public_key(public_pem.encode()).public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()[:16]


def verify(public_pem: str, data: bytes, signature_b64: str) -> bool:
    """True if `signature_b64` (raw r||s) is a valid ECDSA P-256 / SHA-256 signature of `data`."""
    try:
        raw = base64.b64decode(signature_b64, validate=True)
        if len(raw) != 64:
            return False
        public = serialization.load_pem_public_key(public_pem.encode())
        der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        public.verify(der, data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
