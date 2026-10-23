"""CV validation and text extraction (API spec E07, S-06 – S-10).

* Only PDF and DOCX. The file *content* must match its extension (magic bytes);
  the client's filename and Content-Type are never trusted.
* PDFs: pypdf, encrypted files rejected, page count capped.
* DOCX: read with the standard library (zipfile + XML). Entry count and
  uncompressed size are capped to defend against zip bombs. Macros and
  embedded objects are never opened or executed.
* Skills: rule-based match against app/data/skills.txt (no AI, no network).
"""

import hashlib
import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "rules-v1"
ALLOWED_EXTENSIONS = ("pdf", "docx")
_DOCX_MAX_ENTRIES = 2000
_DOCX_MAX_UNCOMPRESSED = 50 * 1024 * 1024
_DOCX_MAX_DOCUMENT_XML = 20 * 1024 * 1024
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class ParsedCV:
    extension: str
    text: str
    sha256: str
    skills: list[str] = field(default_factory=list)
    experience: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)


def unsupported() -> AppError:
    return AppError("UNSUPPORTED_FILE_TYPE", "Unsupported format. Please upload a PDF or DOCX file.", 415)


def unreadable() -> AppError:
    return AppError(
        "CV_UNREADABLE",
        "We couldn't read any text from this CV. Please upload a text-based PDF or DOCX "
        "that isn't password-protected.",
        422,
    )


def sanitize_filename(name: str | None) -> str:
    """Keep only the base name and safe characters; used for display only."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[^\w.\- ()]+", "_", base, flags=re.UNICODE).strip(" .")
    return (base or "cv")[:255]


def extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def detect_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" in names and "word/document.xml" in names:
            return "docx"
    return None


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise unreadable()
        pages = reader.pages[: get_settings().cv_max_pdf_pages]
        return "\n".join((page.extract_text() or "") for page in pages)
    except AppError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        logger.info("PDF could not be parsed: %s", type(exc).__name__)
        raise unreadable() from exc


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > _DOCX_MAX_ENTRIES or sum(i.file_size for i in infos) > _DOCX_MAX_UNCOMPRESSED:
                raise unreadable()
            document = archive.getinfo("word/document.xml")
            if document.file_size > _DOCX_MAX_DOCUMENT_XML:
                raise unreadable()
            xml_bytes = archive.read(document)
        root = ElementTree.fromstring(xml_bytes)
    except AppError:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, RuntimeError, ValueError) as exc:
        # RuntimeError: encrypted zip entries
        logger.info("DOCX could not be parsed: %s", type(exc).__name__)
        raise unreadable() from exc

    paragraphs = []
    for paragraph in root.iter(f"{_W_NS}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{_W_NS}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W_NS}tab":
                parts.append(" ")
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


# --- skills and profile lines -------------------------------------------------


@lru_cache
def load_skills(path: Path) -> tuple[str, ...]:
    skills = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            skills.append(line)
    return tuple(skills)


@lru_cache
def _skill_pattern(skill: str) -> re.Pattern:
    # Very short names (R, Go, C) only match with exact case to avoid false hits.
    flags = 0 if len(skill) <= 2 else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9+#.]){re.escape(skill)}(?![A-Za-z0-9+#])", flags)


def find_skills(text: str, vocabulary: tuple[str, ...], limit: int = 30) -> list[str]:
    found = []
    for skill in vocabulary:
        if _skill_pattern(skill).search(text):
            found.append(skill)
            if len(found) >= limit:
                break
    return found


_SECTION_HEADINGS = {
    "experience": re.compile(r"^(work |professional )?(experience|employment|work history|internships?)\b", re.I),
    "education": re.compile(r"^(education|academic|qualifications)\b", re.I),
    "projects": re.compile(r"^(projects?|personal projects|selected projects)\b", re.I),
}
_ANY_HEADING = re.compile(
    r"^(skills|technical skills|summary|profile|objective|certifications?|languages|interests|"
    r"awards|references|contact|experience|education|projects?)\b", re.I,
)


def extract_profile_lines(text: str, per_section: int = 5) -> dict[str, list[str]]:
    """Best-effort: lines that follow an Experience/Education/Projects heading."""
    sections: dict[str, list[str]] = {name: [] for name in _SECTION_HEADINGS}
    current = None
    for raw in text.splitlines():
        line = raw.strip(" \t•-*·▪●")
        if not line:
            continue
        heading = next((name for name, rx in _SECTION_HEADINGS.items() if rx.match(line) and len(line) < 40), None)
        if heading:
            current = heading
            continue
        if _ANY_HEADING.match(line) and len(line) < 40:
            current = None
            continue
        if current and len(sections[current]) < per_section:
            sections[current].append(line[:200])
    return sections


def parse_cv(data: bytes, filename: str) -> ParsedCV:
    extension = extension_of(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise unsupported()
    if detect_type(data) != extension:
        raise unsupported()

    text = _extract_pdf(data) if extension == "pdf" else _extract_docx(data)
    text = re.sub(r"[ \t ]+", " ", text).strip()
    if len(text) < get_settings().cv_min_text_chars:
        raise unreadable()

    settings = get_settings()
    skills = find_skills(text, load_skills(settings.skills_list_path))
    profile = extract_profile_lines(text)
    return ParsedCV(
        extension=extension,
        text=text,
        sha256=hashlib.sha256(data).hexdigest(),
        skills=skills,
        experience=profile["experience"],
        education=profile["education"],
        projects=profile["projects"],
    )
