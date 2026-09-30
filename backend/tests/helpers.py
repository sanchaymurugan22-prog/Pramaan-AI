"""Shared test helpers: the sample report path and a tiny PDF maker."""

from pathlib import Path

SAMPLE_REPORT = Path(__file__).resolve().parents[2] / "samples" / "sample-ransomware-report.txt"


def make_pdf(page_texts: list[str]) -> bytes:
    """Build a tiny real PDF with one line of text per page (so tests need no PDF files)."""
    return make_pdf_streams([f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET" for text in page_texts])


def make_pdf_streams(streams: list[str]) -> bytes:
    """A PDF with one page per drawing-command stream, e.g. "BT /F1 12 Tf 72 720 Td (Hello) Tj ET"."""
    page_texts = streams
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(len(page_texts)))}] /Count {len(page_texts)} >>",
        3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for i, text in enumerate(page_texts):
        stream = text
        objects[4 + 2 * i] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
        )
        objects[5 + 2 * i] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"

    pdf = b"%PDF-1.4\n"
    offsets = []
    for number in sorted(objects):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n{objects[number]}\nendobj\n".encode()
    xref_at = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return pdf
