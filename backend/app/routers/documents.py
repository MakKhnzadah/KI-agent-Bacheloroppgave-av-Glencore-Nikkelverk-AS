from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.services.document_workflow import process_upload


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    return process_upload(filename=file.filename or "", content=content, content_type=file.content_type)