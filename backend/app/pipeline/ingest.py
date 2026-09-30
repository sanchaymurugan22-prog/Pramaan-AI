"""Step 1 of the pipeline: turn a source (pasted text, .txt, .pdf, .docx) into plain text, page by page.

Page numbers are kept so every fact can point back to "page N" of its source:
  - PDF:   one entry per PDF page
  - Word:  split where Word marked a page break (if the file has none, it is all "page 1")
  - text:  split at form-feed characters (\\f), otherwise all "page 1"

The original file and the extracted pages are saved under data/jobs/<job id>/sources/.
"""

import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per file
SUPPORTED_EXTENSIONS = {".txt": "txt", ".pdf": "pdf", ".docx": "docx"}


class IngestError(Exception):
    """Raised with a friendly message when a source cannot be read."""


@dataclass
class ExtractedSource:
    filename: str
    kind: str            # text (pasted) | txt | pdf | docx
    sha256: str          # fingerprint of the original bytes
    pages: list[str]     # plain text of each page; pages[0] is page 1
    original: bytes      # the file as uploaded (saved next to the extracted text)

    @property
    def chars(self) -> int:
        return sum(len(p) for p in self.pages)


def from_text(text: str) -> ExtractedSource:
    """Text pasted into the web page."""
    data = text.encode("utf-8")
    pages = _split_text_pages(text)
    if not "".join(pages).strip():
        raise IngestError("The pasted text is empty.")
    return ExtractedSource("pasted-text.txt", "text", _sha256(data), pages, data)


def from_file(filename: str, data: bytes) -> ExtractedSource:
    """An uploaded file. Picks the reader from the file extension."""
    ext = Path(filename).suffix.lower()
    kind = SUPPORTED_EXTENSIONS.get(ext)
    if kind is None:
        raise IngestError(f"'{filename}': only .txt, .pdf and .docx files are supported for now.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise IngestError(f"'{filename}' is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise IngestError(f"'{filename}' is empty.")

    if kind == "txt":
        pages = _split_text_pages(_decode_text(data))
    elif kind == "pdf":
        pages = _read_pdf(filename, data)
    else:
        pages = _read_docx(filename, data)

    if not "".join(pages).strip():
        if kind == "pdf":
            raise IngestError(
                f"'{filename}' has no text we can read. It is probably a scanned image; "
                "scanned documents (OCR) are supported in a later stage."
            )
        raise IngestError(f"'{filename}' has no text in it.")
    return ExtractedSource(Path(filename).name, kind, _sha256(data), pages, data)


def save_source(job_id: int, source_id: str, source: ExtractedSource) -> Path:
    """Save the original file and its extracted pages. Returns the path of the pages file."""
    folder = settings.data_dir / "jobs" / str(job_id) / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{source_id}-{_safe_name(source.filename)}").write_bytes(source.original)
    pages_path = folder / f"{source_id}.pages.json"
    pages_path.write_text(
        json.dumps({"filename": source.filename, "pages": source.pages}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return pages_path


def load_pages(pages_path: str | Path) -> list[str]:
    """Read back the pages saved by save_source."""
    return json.loads(Path(pages_path).read_text(encoding="utf-8"))["pages"]


# ---- readers ------------------------------------------------------------------------------


def _decode_text(data: bytes) -> str:
    """Text files come in different encodings; try the common ones."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")  # never fails


def _split_text_pages(text: str) -> list[str]:
    text = text.replace("\r\n", "\n")
    return [page.strip("\n") for page in text.split("\f")]


def _read_pdf(filename: str, data: bytes) -> list[str]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise IngestError(f"'{filename}' is password-protected. Remove the password and upload it again.")
        return [(page.extract_text() or "").strip() for page in reader.pages]
    except IngestError:
        raise
    except (PdfReadError, ValueError, KeyError, OSError) as exc:
        raise IngestError(f"'{filename}' could not be read as a PDF ({exc}).")


def _read_docx(filename: str, data: bytes) -> list[str]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # python-docx raises several different errors for bad files
        raise IngestError(f"'{filename}' could not be read as a Word document ({exc}).")

    pages: list[list[str]] = [[]]
    # Walk the body in order, so paragraphs and tables stay in reading order.
    for block in document.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            xml = block.xml
            # Word stores where pages broke when the file was last saved, and manual page breaks.
            if ("lastRenderedPageBreak" in xml or 'w:type="page"' in xml) and pages[-1]:
                pages.append([])
            text = Paragraph(block, document).text
            if text.strip():
                pages[-1].append(text)
        elif tag == "tbl":
            for row in Table(block, document).rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    pages[-1].append(" | ".join(cells))
    return ["\n".join(lines) for lines in pages]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(filename: str) -> str:
    """Keep file names simple on disk (letters, numbers, dot, dash, underscore)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:80] or "file"
