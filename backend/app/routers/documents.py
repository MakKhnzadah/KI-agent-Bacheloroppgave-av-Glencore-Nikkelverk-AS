from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.document_processing.document_parsing import parse_document
from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT
from app.workflow_db.config import get_repo_root
from app.workflow_db.db import get_connection

router = APIRouter(prefix="/documents", tags=["documents"])

llm_provider = OllamaProvider()
agent = AgentService(llm_provider)


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_filename(name: str) -> str:
    name = Path(name).name  # drop any paths
    name = name.strip().replace(" ", "_")
    name = _FILENAME_SAFE_RE.sub("_", name)
    if not name:
        return "upload"
    return name[:180]


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    upload_id = str(uuid.uuid4())
    original_filename = file.filename
    safe_filename = _sanitize_filename(original_filename)
    content_sha256 = _sha256_bytes(content)

    repo_root = get_repo_root()
    uploads_root = repo_root / "databases" / "data" / "uploads" / upload_id
    uploads_root.mkdir(parents=True, exist_ok=True)
    stored_path = uploads_root / safe_filename
    stored_path.write_bytes(content)

    try:
        processed_text = parse_document(original_filename, content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    normalized_id = str(uuid.uuid4())
    normalized_sha256 = _sha256_text(processed_text)

    try:
        suggestions = agent.process_document(STRUCTURING_AGENT_PROMPT, processed_text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}")

    suggestion_id = str(uuid.uuid4())

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO uploads (upload_id, original_filename, content_type, size_bytes, sha256, stored_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    original_filename,
                    file.content_type,
                    len(content),
                    content_sha256,
                    str(stored_path.as_posix()),
                ),
            )
            conn.execute(
                """
                INSERT INTO normalized_documents (normalized_id, upload_id, text, sha256)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_id, upload_id, processed_text, normalized_sha256),
            )
            conn.execute(
                """
                INSERT INTO suggestions (suggestion_id, upload_id, suggestion_json, model, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (suggestion_id, upload_id, suggestions, llm_provider.model, "draft"),
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist workflow data: {exc}")

    return {
        "upload_id": upload_id,
        "suggestion_id": suggestion_id,
        "suggestions": suggestions,
        "status": "draft",
    }