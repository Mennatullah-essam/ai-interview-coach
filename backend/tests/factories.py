"""Synthetic test files (spec S-34: tests never use real CVs).

Both builders use only the standard library, so the tests need no PDF or
Word tooling installed.
"""

import io
import zipfile

SAMPLE_CV_TEXT = [
    "Jordan Example",
    "Summary",
    "Machine learning engineer who enjoys building reliable data products.",
    "Skills",
    "Python, PyTorch, FastAPI, SQL, Docker, React and Git.",
    "Experience",
    "ML Engineer Intern - Example Analytics (2025)",
    "Built a ticket classifier with scikit-learn and deployed it with Docker.",
    "Education",
    "B.Sc. Computer Science - Example University",
    "Projects",
    "Interview practice web app with React and PostgreSQL.",
]


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines: list[str] | None = None) -> bytes:
    """A small, valid, text-based PDF (one page, Helvetica)."""
    lines = SAMPLE_CV_TEXT if lines is None else lines
    content_lines = ["BT", "/F1 11 Tf", "14 TL", "50 780 Td"]
    for line in lines:
        content_lines.append(f"({_pdf_escape(line)}) Tj T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def make_docx(lines: list[str] | None = None) -> bytes:
    """A minimal, valid DOCX containing one paragraph per line."""
    lines = SAMPLE_CV_TEXT if lines is None else lines
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraphs = "".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{line.replace('&', '&amp;').replace('<', '&lt;')}</w:t></w:r></w:p>"
        for line in lines
    )
    document = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{ns}"><w:body>{paragraphs}</w:body></w:document>'
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


GOOD_TECHNICAL_ANSWER = (
    "First I would check how imbalanced the classes are, because accuracy is misleading here. "
    "I would use precision, recall and F1, try SMOTE oversampling and class weights, and keep a "
    "stratified split. For example, on a churn project this raised recall from 0.42 to 0.71. "
    "The trade-off is more false positives, so I tune the decision threshold with the business."
)
