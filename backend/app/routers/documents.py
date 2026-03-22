from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.document_processing.document_parsing import parse_document
from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT
from app.workflow_db.config import get_repo_root
from app.workflow_db.db import get_connection

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
_PROCESSING_MODEL_MARKER = "__processing__"

llm_provider = OllamaProvider()
agent = AgentService(llm_provider)


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_ALLOWED_CATEGORIES = {"Sikkerhet", "Vedlikehold", "Miljø", "Kvalitet", "Prosedyre", "Annet"}


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


def _fallback_structured_document(original_filename: str, content: str) -> str:
    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    body = (content or "").strip() or "Innhold ikke tilgjengelig."
    return (
        "---\n"
        f"title: \"{safe_title}\"\n"
        "tags: []\n"
        "category: \"Annet\"\n"
        "review_status: \"pending\"\n"
        "confidence_score: 0.0\n"
        "---\n\n"
        f"{body}\n"
    )


def _parse_frontmatter(markdown_text: str) -> tuple[dict[str, str], str] | tuple[None, None]:
    match = _FRONTMATTER_RE.match((markdown_text or "").strip())
    if not match:
        return None, None

    yaml_block = match.group(1)
    body = (match.group(2) or "").strip()
    fields: dict[str, str] = {}

    for line in yaml_block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")

    return fields, body


def _validate_structured_suggestion(suggestion: str) -> str | None:
    fields, body = _parse_frontmatter(suggestion)
    if fields is None:
        return "Missing or invalid YAML frontmatter"

    required = {"title", "tags", "category", "review_status", "confidence_score"}
    missing = sorted(required - set(fields.keys()))
    if missing:
        return f"Missing YAML keys: {', '.join(missing)}"

    if fields["review_status"] != "pending":
        return "review_status must be 'pending'"

    if fields["category"] not in _ALLOWED_CATEGORIES:
        return f"Invalid category '{fields['category']}'"

    try:
        confidence = float(fields["confidence_score"])
    except ValueError:
        return "confidence_score must be a number between 0.0 and 1.0"

    if confidence < 0.0 or confidence > 1.0:
        return "confidence_score must be between 0.0 and 1.0"

    if not body:
        return "Structured markdown body is empty"

    return None


def _generate_suggestion_async(suggestion_id: str, original_filename: str, processed_text: str) -> None:
    """Generate structured suggestion in background and update the existing row."""
    try:
        suggestions = agent.process_document(STRUCTURING_AGENT_PROMPT, processed_text)
        validation_error = _validate_structured_suggestion(suggestions)
        if validation_error:
            logger.warning("Suggestion %s failed validation: %s", suggestion_id, validation_error)
            suggestions = _fallback_structured_document(original_filename, processed_text)
    except Exception:
        logger.exception("Background suggestion generation failed for %s", suggestion_id)
        suggestions = _fallback_structured_document(original_filename, processed_text)

    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE suggestions
                SET suggestion_json = ?, model = ?
                WHERE suggestion_id = ?
                """,
                (suggestions, llm_provider.model, suggestion_id),
            )
    except Exception:
        logger.exception("Failed to persist background suggestion for %s", suggestion_id)


@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
    suggestion_id = str(uuid.uuid4())
    fallback_suggestion = _fallback_structured_document(original_filename, processed_text)

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
                (suggestion_id, upload_id, fallback_suggestion, _PROCESSING_MODEL_MARKER, "draft"),
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist workflow data: {exc}")

    # Perform expensive AI structuring after returning the upload response.
    background_tasks.add_task(_generate_suggestion_async, suggestion_id, original_filename, processed_text)

    return {
        "upload_id": upload_id,
        "suggestion_id": suggestion_id,
        "structured_draft": fallback_suggestion,
        "suggestion_addon": "",
        "suggestions": fallback_suggestion,
        "status": "draft",
        "llm_fallback_used": True,
        "llm_error": "Background generation in progress",
    }