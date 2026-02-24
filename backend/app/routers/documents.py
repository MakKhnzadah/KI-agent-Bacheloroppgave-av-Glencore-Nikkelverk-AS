from fastapi import APIRouter,UploadFile, File
from  app.document_processing.document_parsing import parse_document


router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    # Process the text using the txt_parser function
    processed_data = parse_document(file.filename, content)
    
    return {"processed_data": processed_data}