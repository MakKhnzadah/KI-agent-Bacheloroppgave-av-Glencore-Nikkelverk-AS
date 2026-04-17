import io
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def docx_parser(content: bytes) -> str:
    """Extract plain text from a DOCX file.

    Preserves paragraph breaks to keep the original document readable when shown as text.

    Important: many handbooks store critical procedures/limits in tables. We therefore
    extract both paragraphs and table cells (in document order).
    """

    def iter_block_items(doc: Document):
        body = doc.element.body
        for child in body.iterchildren():
            tag = child.tag
            if tag.endswith("}p"):
                yield Paragraph(child, doc)
            elif tag.endswith("}tbl"):
                yield Table(child, doc)

    doc = Document(io.BytesIO(content))
    paragraphs: list[str] = []

    def clean_line(text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""
        # Normalize intra-line whitespace but keep paragraph boundaries.
        raw = re.sub(r"[\t\f\v ]+", " ", raw)
        return raw.strip()

    seen_table_rows: set[str] = set()

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            raw = clean_line(block.text)
            if raw:
                paragraphs.append(raw)
            continue

        if isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    cell_text = clean_line(cell.text)
                    if cell_text:
                        cells.append(cell_text)
                if not cells:
                    continue
                # De-duplicate identical rows (common when Word merges cells internally).
                row_key = " | ".join(cells)
                if row_key in seen_table_rows:
                    continue
                seen_table_rows.add(row_key)
                paragraphs.append(row_key)

    return "\n\n".join(paragraphs).strip()
