from __future__ import annotations

import io
import re

from docx import Document


def docx_parser(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    text = "\n".join((p.text or "") for p in doc.paragraphs)
    return re.sub(r"\s+", " ", text).strip()
