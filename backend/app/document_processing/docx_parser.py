import io
import re

from docx import Document


def docx_parser(content: bytes) -> str:
    """Extract plain text from a DOCX file and normalize whitespace."""
    doc = Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text)
    return re.sub(r"\s+", " ", text).strip()
