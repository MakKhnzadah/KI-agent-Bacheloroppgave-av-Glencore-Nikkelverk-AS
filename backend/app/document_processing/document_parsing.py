import os
from app.document_processing.txt_parser import txt_parser
from app.document_processing.pdf_parser import pdf_parser


PARSERS = {
    '.txt': txt_parser,
    '.pdf': pdf_parser,
}

def parse_document(filename: str, content: bytes) :
    extension = os.path.splitext(filename.lower())[1]

    if extension not in PARSERS:
        raise ValueError("Unsuppoerted file type")
    
    parser = PARSERS[extension]
 
    if extension == ".txt":
        return parser(content.decode("utf-8"))
    return parser(content)