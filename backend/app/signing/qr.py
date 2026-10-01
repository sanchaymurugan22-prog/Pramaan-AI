"""QR codes for signed files. The QR holds only the public verify address and the record number,
e.g. http://localhost:8090/?r=PRM-2026-000001 (VERIFY_BASE_URL in .env). Nothing secret."""

import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from app.config import settings


def verify_url(record_no: str) -> str:
    return f"{settings.verify_base_url}/?r={record_no}"


def qr_image(text: str, box_size: int = 10):
    """A black-on-white QR code as a Pillow image (medium error correction, 4-module quiet zone)."""
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=4)
    code.add_data(text)
    code.make(fit=True)
    return code.make_image(fill_color="black", back_color="white").get_image().convert("RGB")


def qr_png(text: str, box_size: int = 10) -> bytes:
    buffer = io.BytesIO()
    qr_image(text, box_size).save(buffer, "PNG")
    return buffer.getvalue()
