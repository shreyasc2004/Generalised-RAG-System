import io
from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from rag.loaders import load_document


@pytest.mark.parametrize("suffix,content,expected", [
    (".txt", "\ufeffHello text", "Hello text"),
    (".md", "# Heading\nBody", "Heading"),
    (".json", '{"name": "Sample"}', "Sample"),
    (".csv", "name,role\nAda,Engineer", "role: Engineer"),
    (".html", "<h1>Visible</h1><script>hidden()</script><p>Body</p>", "Visible"),
])
def test_text_formats(suffix, content, expected):
    sections = load_document(Path("doc" + suffix), content.encode("utf-8"))
    assert expected in sections[0].text
    assert "hidden()" not in sections[0].text


def test_docx_paragraphs_and_tables():
    doc = Document()
    doc.add_paragraph("Document policy")
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "Table policy"
    stream = io.BytesIO()
    doc.save(stream)
    text = load_document(Path("doc.docx"), stream.getvalue())[0].text
    assert "Document policy" in text and "Table policy" in text


def test_pdf_preserves_page_numbers():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 50 700 Td (PDF policy text) Tj ET")
    page[NameObject("/Contents")] = content
    stream = io.BytesIO()
    writer.write(stream)
    sections = load_document(Path("doc.pdf"), stream.getvalue())
    assert len(sections) == 1 and sections[0].page == 2
    assert "PDF policy text" in sections[0].text


def test_empty_and_malformed_inputs():
    with pytest.raises(ValueError, match="No extractable text"):
        load_document(Path("empty.txt"), b"  ")
    with pytest.raises(ValueError):
        load_document(Path("broken.json"), b"{broken")
    with pytest.raises(UnicodeDecodeError):
        load_document(Path("binary.txt"), b"\xff\xfe")

