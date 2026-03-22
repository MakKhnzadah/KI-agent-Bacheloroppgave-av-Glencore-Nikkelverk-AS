import os
from app.document_processing.txt_parser import txt_parser
from app.document_processing.pdf_parser import pdf_parser
from app.document_processing.docx_parser import docx_parser


PARSERS = {
    '.txt': txt_parser,
    '.pdf': pdf_parser,
    '.docx': docx_parser,
}

def parse_document(filename: str, content: bytes) :
    extension = os.path.splitext(filename.lower())[1]

    if extension not in PARSERS:
        supported = ", ".join(sorted(PARSERS.keys()))
        raise ValueError(f"Unsupported file type '{extension}'. Supported types: {supported}")
    
    parser = PARSERS[extension]
 
    if extension == ".txt":
        return parser(content.decode("utf-8"))
    return parser(content)