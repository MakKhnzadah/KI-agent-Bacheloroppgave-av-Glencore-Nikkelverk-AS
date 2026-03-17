from __future__ import annotations

import os

from app.document_processing.docx_parser import docx_parser
from app.document_processing.eml_parser import eml_parser
from app.document_processing.pdf_parser import pdf_parser
from app.document_processing.txt_parser import txt_parser


PARSERS = {
    '.txt': txt_parser,
    '.pdf': pdf_parser,
    '.md': txt_parser,
    '.docx': docx_parser,
    '.eml': eml_parser,
}

def parse_document(filename: str, content: bytes) -> str:
    extension = os.path.splitext(filename.lower())[1]

    if extension not in PARSERS:
        raise ValueError(f"Unsupported file type: {extension}")
    
    parser = PARSERS[extension]
 
    if extension in {".txt", ".md"}:
        return parser(content.decode("utf-8", errors="replace"))
    return parser(content)