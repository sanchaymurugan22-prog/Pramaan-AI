"""Step 1 of the pipeline: turn a source (pasted text, .txt, .pdf, .docx) into plain text, page by page.

Page numbers are kept so every fact can point back to "page N" of its source:
  - PDF:   one entry per PDF page
  - Word:  split where Word marked a page break (if the file has none, it is all "page 1")
  - text:  split at form-feed characters (\\f), otherwise all "page 1"

Stage 6A (prompt-injection shield): hidden characters (zero-width, bidi controls) are removed from
every page, and hidden text in Word files (white, tiny or "Hidden" text) and PDFs (invisible, white or
tiny text) is left out of the page text. What was removed is kept in `notes`, and the Safety check
shows it (see app/safety/shield.py).

The original file and the extracted pages are saved under data/jobs/<job id>/sources/.
"""

import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from math import hypot
from pathlib import Path

from app.config import settings
from app.safety.shield import strip_hidden_chars

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
    notes: list[dict] = field(default_factory=list)  # hidden characters / hidden text that were removed

    @property
    def chars(self) -> int:
        return sum(len(p) for p in self.pages)


def from_text(text: str) -> ExtractedSource:
    """Text pasted into the web page."""
    data = text.encode("utf-8")
    pages, notes = _remove_hidden_chars(_split_text_pages(text))
    if not "".join(pages).strip():
        raise IngestError("The pasted text is empty.")
    return ExtractedSource("pasted-text.txt", "text", _sha256(data), pages, data, notes)


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

    hidden_text: list[dict] = []
    if kind == "txt":
        pages = _split_text_pages(_decode_text(data))
    elif kind == "pdf":
        pages, hidden_text = _read_pdf(filename, data)
    else:
        pages, hidden_text = _read_docx(filename, data)
    pages, notes = _remove_hidden_chars(pages)

    if not "".join(pages).strip():
        if kind == "pdf":
            raise IngestError(
                f"'{filename}' has no text we can read. It is probably a scanned image; "
                "scanned documents (OCR) are supported in a later stage."
            )
        raise IngestError(f"'{filename}' has no text in it.")
    return ExtractedSource(Path(filename).name, kind, _sha256(data), pages, data, hidden_text + notes)


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


def _remove_hidden_chars(pages: list[str]) -> tuple[list[str], list[dict]]:
    """Strip zero-width and direction-control characters from every page; one note per page that had any."""
    clean_pages, notes = [], []
    for number, page in enumerate(pages, start=1):
        if number == 1 and page.startswith("\ufeff"):
            page = page[1:]  # a byte-order mark at the very start is normal, not hidden text
        clean, removed = strip_hidden_chars(page)
        clean_pages.append(clean)
        if removed:
            notes.append({"kind": "hidden_characters", "page": number, "position": removed[0][0],
                          "positions": [position for position, _ in removed], "chars": "".join(c for _, c in removed)})
    return clean_pages, notes


def _read_pdf(filename: str, data: bytes) -> tuple[list[str], list[dict]]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise IngestError(f"'{filename}' is password-protected. Remove the password and upload it again.")
        pages, hidden = [], []
        for number, page in enumerate(reader.pages, start=1):
            watcher = _PdfHiddenText()
            text = (page.extract_text(visitor_operand_before=watcher.before, visitor_text=watcher.text) or "").strip()
            for reason, piece in watcher.pieces():
                text = _remove_piece(text, piece)
                hidden.append({"kind": "hidden_text", "file_kind": "PDF", "page": number, "text": piece.strip(),
                               "reason": reason})
            pages.append(text.strip())
        return pages, hidden
    except IngestError:
        raise
    except (PdfReadError, ValueError, KeyError, OSError) as exc:
        raise IngestError(f"'{filename}' could not be read as a PDF ({exc}).")


class _PdfHiddenText:
    """Watches a PDF page being read and notes text a person cannot see: invisible (text render mode 3),
    white, or tiny (under 3 pt). pypdf passes each drawing command to before() and each piece of text
    to text(). A piece mixing visible and hidden text is treated as visible."""

    TINY_POINTS = 3.0

    def __init__(self):
        self.render_mode, self.fill, self.font_size, self.saved = 0, (0.0, 0.0, 0.0), None, []
        self.pending: list[str | None] = []     # hidden reason (or None) of each text command since the last piece
        self.found: list[tuple[str, str]] = []  # (reason, text)

    def before(self, operator, operands, cm, tm) -> None:
        numbers = [float(o) for o in operands if isinstance(o, (int, float))]
        if operator == b"q":
            self.saved.append((self.render_mode, self.fill))
        elif operator == b"Q" and self.saved:
            self.render_mode, self.fill = self.saved.pop()
        elif operator == b"Tf" and numbers:
            self.font_size = numbers[-1]
        elif operator == b"Tr" and numbers:
            self.render_mode = int(numbers[0])
        elif operator in (b"rg", b"g", b"k", b"sc", b"scn"):
            if len(numbers) == 1:
                self.fill = (numbers[0],) * 3
            elif len(numbers) == 3:
                self.fill = tuple(numbers)
            elif len(numbers) == 4:  # CMYK
                c, m, y, k = numbers
                self.fill = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        elif operator in (b"Tj", b"TJ", b"'", b'"'):
            size = self._size(cm, tm)
            if self.render_mode in (3, 7):
                self.pending.append("invisible text")
            elif min(self.fill) >= 0.95:
                self.pending.append("white text")
            elif size is not None and size < self.TINY_POINTS:
                self.pending.append(f"tiny text ({size:.1f} pt)")
            else:
                self.pending.append(None)

    def _size(self, cm, tm) -> float | None:
        """The height the text is drawn at, in points (font size scaled by the text and page matrices)."""
        if self.font_size is None:
            return None
        return self.font_size * hypot(tm[2], tm[3]) * hypot(cm[2], cm[3])

    def text(self, text, cm, tm, font, font_size) -> None:
        reasons, self.pending = self.pending, []
        if text.strip() and reasons and all(reasons):
            self.found.append((reasons[0], text))

    def pieces(self) -> list[tuple[str, str]]:
        """Hidden text found on the page, next to each other pieces joined."""
        joined: list[tuple[str, str]] = []
        for reason, text in self.found:
            if joined and joined[-1][0] == reason:
                joined[-1] = (reason, joined[-1][1] + text)
            else:
                joined.append((reason, text))
        return [(reason, text) for reason, text in joined if len(text.strip()) >= 3]


def _remove_piece(text: str, piece: str) -> str:
    """Take hidden text out of the page text (each line of it, first place found)."""
    for line in (line.strip() for line in piece.splitlines()):
        if len(line) >= 3 and line in text:
            text = text.replace(line, "", 1)
    return re.sub(r"\n{3,}", "\n\n", text)


def _read_docx(filename: str, data: bytes) -> tuple[list[str], list[dict]]:
    import docx
    from docx.table import Table

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # python-docx raises several different errors for bad files
        raise IngestError(f"'{filename}' could not be read as a Word document ({exc}).")

    pages: list[list[str]] = [[]]
    hidden: list[dict] = []

    def visible(paragraph_element) -> str:
        text, pieces = _visible_docx_text(paragraph_element)
        hidden.extend({"kind": "hidden_text", "file_kind": "Word", "page": len(pages), "text": piece, "reason": reason}
                      for reason, piece in pieces)
        return text

    # Walk the body in order, so paragraphs and tables stay in reading order.
    for block in document.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            xml = block.xml
            # Word stores where pages broke when the file was last saved, and manual page breaks.
            if ("lastRenderedPageBreak" in xml or 'w:type="page"' in xml) and pages[-1]:
                pages.append([])
            text = visible(block)
            if text.strip():
                pages[-1].append(text)
        elif tag == "tbl":
            for row in Table(block, document).rows:
                cells = ["\n".join(visible(p._p) for p in cell.paragraphs).strip() for cell in row.cells]
                if any(cells):
                    pages[-1].append(" | ".join(cells))
    return ["\n".join(lines) for lines in pages], hidden


def _visible_docx_text(paragraph_element) -> tuple[str, list[tuple[str, str]]]:
    """A Word paragraph's text without hidden runs, and the hidden runs as [(reason, text)].
    Same runs, same order as python-docx's paragraph.text (runs and links)."""
    from docx.text.run import Run

    shown: list[str] = []
    pieces: list[tuple[str, str]] = []
    for element in paragraph_element.xpath("./w:r | ./w:hyperlink/w:r"):
        run = Run(element, None)
        text = run.text
        reason = _docx_hidden_reason(run) if text.strip() else None
        if reason is None:
            shown.append(text)
        elif pieces and pieces[-1][0] == reason and not shown[-1:]:
            pieces[-1] = (reason, pieces[-1][1] + text)
        else:
            pieces.append((reason, text))
    return "".join(shown), [(reason, text.strip()) for reason, text in pieces if text.strip()]


def _docx_hidden_reason(run) -> str | None:
    """Why a Word run cannot be seen by a reader, or None if it can."""
    font = run.font
    if font.hidden:
        return "hidden text (Word's Hidden setting)"
    if font.size is not None and font.size.pt < 4:
        return f"tiny text ({font.size.pt:g} pt)"
    try:
        rgb = font.color.rgb if font.color is not None and font.color.type is not None else None
    except (AttributeError, ValueError):
        rgb = None
    background = font.highlight_color is not None or run._r.xpath("./w:rPr/w:shd")
    if rgb is not None and min(rgb[0], rgb[1], rgb[2]) >= 0xF0 and not background:
        return "white text"
    return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(filename: str) -> str:
    """Keep file names simple on disk (letters, numbers, dot, dash, underscore)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", filename)[:80] or "file"
