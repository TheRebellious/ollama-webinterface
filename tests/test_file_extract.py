"""Unit tests for Office Open XML file extraction (TE-001, SE-002)."""
import base64
import io
import zipfile
import pytest

from ollama_console.file_extract import (
    extract_uploaded_file,
    get_extension,
    FileExtractionError,
)


def _create_mock_docx(text_content="Hello world from docx"):
    """Create a minimal valid DOCX zip archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p><w:r><w:t>{text_content}</w:t></w:r></w:p>
            </w:body>
        </w:document>"""
        z.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


def _create_mock_xlsx(cells=("Alpha", "Beta", "Gamma")):
    """Create a minimal valid XLSX zip archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # shared strings
        sst_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
            <si><t>Alpha</t></si>
            <si><t>Beta</t></si>
            <si><t>Gamma</t></si>
        </sst>"""
        z.writestr("xl/sharedStrings.xml", sst_xml)

        sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
            <sheetData>
                <row r="1">
                    <c r="A1" t="s"><v>0</v></c>
                    <c r="B1" t="s"><v>1</v></c>
                    <c r="C1" t="s"><v>2</v></c>
                </row>
            </sheetData>
        </worksheet>"""
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def _create_mock_pptx(slide_text="Slide 1 Content"):
    """Create a minimal valid PPTX zip archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        slide_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
               xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
            <p:cSld>
                <p:spTree>
                    <p:sp><p:txBody><a:p><a:r><a:t>{slide_text}</a:t></a:r></a:p></p:txBody></p:sp>
                </p:spTree>
            </p:cSld>
        </p:sld>"""
        z.writestr("ppt/slides/slide1.xml", slide_xml)
    return buf.getvalue()


class TestFileExtraction:
    """Test extract_uploaded_file with supported types and error conditions."""

    def test_extract_docx_success(self):
        content = _create_mock_docx("Important Test Document")
        b64 = base64.b64encode(content).decode("ascii")
        res = extract_uploaded_file("doc.docx", b64, 10 * 1024 * 1024)
        assert res["filename"] == "doc.docx"
        assert res["extension"] == "docx"
        assert "Important Test Document" in res["content"]

    def test_extract_xlsx_success(self):
        content = _create_mock_xlsx()
        b64 = base64.b64encode(content).decode("ascii")
        res = extract_uploaded_file("data.xlsx", b64, 10 * 1024 * 1024)
        assert res["extension"] == "xlsx"
        assert "Alpha" in res["content"]
        assert "Beta" in res["content"]

    def test_extract_pptx_success(self):
        content = _create_mock_pptx("Keynote Presentation")
        b64 = base64.b64encode(content).decode("ascii")
        res = extract_uploaded_file("slides.pptx", b64, 10 * 1024 * 1024)
        assert res["extension"] == "pptx"
        assert "Keynote Presentation" in res["content"]

    def test_unsupported_extension_raises_error(self):
        with pytest.raises(FileExtractionError, match="Unsupported Office"):
            extract_uploaded_file("script.py", "c3VwZXI=", 1024)

    def test_invalid_base64_raises_error(self):
        with pytest.raises(FileExtractionError, match="Invalid base64"):
            extract_uploaded_file("file.docx", "invalid!!!base64", 1024)

    def test_file_larger_than_max_bytes_rejected(self):
        content = _create_mock_docx("Small")
        b64 = base64.b64encode(content).decode("ascii")
        with pytest.raises(FileExtractionError, match="larger than"):
            extract_uploaded_file("file.docx", b64, 10)  # max 10 bytes

    def test_corrupted_zip_archive_raises_error(self):
        fake_content = b"Not a zip file at all"
        b64 = base64.b64encode(fake_content).decode("ascii")
        with pytest.raises(FileExtractionError, match="could not be extracted"):
            extract_uploaded_file("corrupt.docx", b64, 1024)

    def test_get_extension_helper(self):
        assert get_extension("file.DOCX") == "docx"
        assert get_extension("path/to/my.file.xlsx") == "xlsx"
        assert get_extension("no_extension") == ""
