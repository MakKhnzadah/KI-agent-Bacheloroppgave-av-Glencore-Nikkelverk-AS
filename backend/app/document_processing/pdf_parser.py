import re 
import pdfplumber
import io

def pdf_parser(content: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    # Remove whitespace and newlines
    remove_whitespace = re.sub(r'\s+', ' ', text).strip()

    
    return remove_whitespace