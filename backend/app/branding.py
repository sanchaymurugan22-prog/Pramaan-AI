"""The letterhead printed on every exported file (Stage 9B, design 35): the office's name and logo.

The Admin sets them on Templates & letterheads. Until then the office name is ISSUING_OFFICE from .env
(the same name the signed records give as "Issued by") and there is no logo.

The logo is checked with Pillow (a real PNG or JPEG, at most 2 MB), made at most 600 pixels wide, saved
as PNG, and stored encrypted like every other file (data/branding/logo.png).
"""

import io

from PIL import Image, UnidentifiedImageError

from app import app_settings, crypto
from app.config import settings

LOGO_PATH = settings.data_dir / "branding" / "logo.png"
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_WIDTH = 600


class LogoError(ValueError):
    """The upload is not a usable logo; the message says why."""


def office_name() -> str:
    return app_settings.get("letterhead").get("office_name") or settings.issuing_office


def logo_png() -> bytes | None:
    if not app_settings.get("letterhead").get("has_logo") or not LOGO_PATH.exists():
        return None
    try:
        return crypto.read_file(LOGO_PATH)
    except Exception:  # a damaged file must not stop every export
        return None


def clean_logo(data: bytes) -> bytes:
    """A checked, resized PNG from an uploaded PNG or JPEG."""
    if len(data) > MAX_LOGO_BYTES:
        raise LogoError("The logo must be at most 2 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()  # a broken or fake image fails here
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise LogoError("That is not a PNG or JPEG image.") from None
    if image.format not in ("PNG", "JPEG"):
        raise LogoError("Upload the logo as a PNG or JPEG image.")
    if image.width < 32 or image.height < 32:
        raise LogoError("The logo is too small (at least 32 × 32 pixels).")
    image = image.convert("RGBA")
    if image.width > MAX_LOGO_WIDTH:
        image = image.resize((MAX_LOGO_WIDTH, round(image.height * MAX_LOGO_WIDTH / image.width)), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def save_logo(data: bytes) -> None:
    LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
    crypto.write_file(LOGO_PATH, clean_logo(data))


def remove_logo() -> None:
    LOGO_PATH.unlink(missing_ok=True)
