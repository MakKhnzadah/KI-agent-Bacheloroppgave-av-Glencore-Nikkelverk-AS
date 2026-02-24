import re

def txt_parser(text: str) -> str:
    # Remove extra whitespace and newlines
    #this is just to have bare minimum for processing .txt files
    remove_whitespace = re.sub(r'\s+', ' ', text).strip()
    
    # Add more processes here afterwards
    return remove_whitespace