import base64
import io
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree


OFFICE_EXTENSIONS = {"docx", "xlsx", "pptx"}


class FileExtractionError(Exception):
    pass


def extract_uploaded_file(filename, content_base64, max_bytes):
    extension = get_extension(filename)
    if extension not in OFFICE_EXTENSIONS:
        raise FileExtractionError(f"Unsupported Office file type: {extension}")

    try:
        content = base64.b64decode(content_base64, validate=True)
    except ValueError as error:
        raise FileExtractionError("Invalid base64 file content") from error

    if len(content) > max_bytes:
        raise FileExtractionError(f"File is larger than {max_bytes} bytes")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if extension == "docx":
                text = extract_docx(archive)
            elif extension == "xlsx":
                text = extract_xlsx(archive)
            else:
                text = extract_pptx(archive)
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError) as error:
        raise FileExtractionError("Office file could not be extracted") from error

    return {
        "filename": filename,
        "extension": extension,
        "content": text.strip(),
    }


def get_extension(filename):
    return PurePosixPath(filename.lower()).suffix.lstrip(".")


def extract_docx(archive):
    members = set(archive.namelist())
    parts = ["word/document.xml"]
    parts.extend(sorted(name for name in members if name.startswith("word/header") and name.endswith(".xml")))
    parts.extend(sorted(name for name in members if name.startswith("word/footer") and name.endswith(".xml")))
    return "\n\n".join(text_from_xml_part(archive, part) for part in parts if part in members)


def extract_pptx(archive):
    slides = sorted(
        name for name in archive.namelist()
        if name.startswith("ppt/slides/slide") and name.endswith(".xml")
    )
    chunks = []
    for index, slide in enumerate(slides, start=1):
        text = text_from_xml_part(archive, slide)
        if text:
            chunks.append(f"Slide {index}\n{text}")
    return "\n\n".join(chunks)


def extract_xlsx(archive):
    shared_strings = read_shared_strings(archive)
    sheets = sorted(
        name for name in archive.namelist()
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
    )
    chunks = []

    for index, sheet in enumerate(sheets, start=1):
        rows = rows_from_sheet(archive, sheet, shared_strings)
        if rows:
            chunks.append(f"Sheet {index}\n" + "\n".join(rows))

    return "\n\n".join(chunks)


def text_from_xml_part(archive, member):
    root = read_xml(archive, member)
    paragraphs = []

    for paragraph in root.iter():
        if not paragraph.tag.endswith("}p"):
            continue
        text = "".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t"))
        if text.strip():
            paragraphs.append(text.strip())

    if paragraphs:
        return "\n".join(paragraphs)

    return " ".join(node.text.strip() for node in root.iter() if node.text and node.text.strip())


def read_shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = read_xml(archive, "xl/sharedStrings.xml")
    strings = []
    for item in root:
        text = "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
        strings.append(text)
    return strings


def rows_from_sheet(archive, member, shared_strings):
    root = read_xml(archive, member)
    rows = []

    for row in root.iter():
        if not row.tag.endswith("}row"):
            continue

        cells = []
        for cell in row:
            if not cell.tag.endswith("}c"):
                continue
            cells.append(cell_text(cell, shared_strings))

        if any(value for value in cells):
            rows.append("\t".join(cells))

    return rows


def cell_text(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    value = None

    for child in cell:
        if child.tag.endswith("}v"):
            value = child.text
            break
        if child.tag.endswith("}is"):
            return "".join(node.text or "" for node in child.iter() if node.tag.endswith("}t"))

    if value is None:
        return ""

    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value

    return value


def read_xml(archive, member):
    with archive.open(member) as file:
        return ElementTree.fromstring(file.read())
