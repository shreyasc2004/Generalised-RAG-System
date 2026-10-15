from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


SUPPORTED = {".txt", ".md", ".markdown", ".pdf", ".docx", ".csv", ".json", ".html", ".htm"}


@dataclass(frozen=True)
class Section:
    text: str
    page: int | None = None


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def load_document(path: Path, data: bytes) -> list[Section]:
    """Parse a byte snapshot so the checksum matches exactly what is indexed."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are unsupported; supply an unlocked copy.")
        sections = [Section(page.extract_text() or "", i + 1) for i, page in enumerate(reader.pages)]
    elif suffix == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in doc.paragraphs]
        for table in doc.tables:
            parts.extend(" | ".join(cell.text for cell in row.cells) for row in table.rows)
        sections = [Section("\n".join(parts))]
    else:
        text = data.decode("utf-8-sig")
        if suffix == ".json":
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        elif suffix == ".csv":
            rows = csv.reader(io.StringIO(text))
            header = next(rows, [])
            text = "\n".join(
                "; ".join(f"{header[i] if i < len(header) else f'column_{i + 1}'}: {cell}" for i, cell in enumerate(row))
                for row in rows
            )
        elif suffix in {".html", ".htm"}:
            parser = _HTMLText()
            parser.feed(text)
            text = "".join(parser.parts)
        elif suffix not in SUPPORTED:
            raise ValueError(f"Unsupported format: {suffix}")
        sections = [Section(text)]
    sections = [Section(s.text.replace("\x00", "").strip(), s.page) for s in sections if s.text.strip()]
    if not sections:
        raise ValueError("No extractable text. Scanned PDFs need OCR before ingestion.")
    return sections

