from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
import yaml
from yaml import YAMLError

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.document_processing.document_parsing import parse_document
from app.services.revised_suggestion import (
    fallback_structured_document_short,
    generate_revised_suggestion,
    is_effectively_empty,
    unreadable_pdf_message,
)
from app.workflow_db.config import get_repo_root
from app.workflow_db.db import get_connection

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

_STRUCTURING_PROMPT_VERSION = os.getenv("STRUCTURING_PROMPT_VERSION", "2026-04-14-rs4").strip() or "2026-04-14-rs4"

llm_provider = OllamaProvider()
agent = AgentService(llm_provider)

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_UPLOAD_CATEGORY_MAP = {
    "sikkerhet": "Sikkerhet",
    "vedlikehold": "Vedlikehold",
    "miljo": "Miljø",
    "miljø": "Miljø",
    "kvalitet": "Kvalitet",
    "prosedyre": "Prosedyre",
    "annet": "Annet",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_filename(name: str) -> str:
    name = Path(name).name
    name = name.strip().replace(" ", "_")
    name = _FILENAME_SAFE_RE.sub("_", name)
    if not name:
        return "upload"
    return name[:180]


def _normalize_selected_category(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    mapped = _UPLOAD_CATEGORY_MAP.get(raw.lower())
    if mapped:
        return mapped
    return None


def _split_front_matter(doc: str) -> tuple[dict, str]:
    text = (doc or "").lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}, doc

    lines = text.splitlines(keepends=True)
    if not lines or lines[0] != "---\n":
        return {}, doc

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, doc

    front_raw = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :]).lstrip("\n")

    try:
        parsed = yaml.safe_load(front_raw) or {}
        if isinstance(parsed, dict):
            return parsed, body
    except YAMLError:
        pass
    return {}, doc


def _apply_selected_category(suggestion_text: str, selected_category: str | None) -> str:
    if not selected_category:
        return suggestion_text

    front, body = _split_front_matter(suggestion_text)
    if front:
        front_out = dict(front)
        front_out["category"] = selected_category
        rendered_front = yaml.safe_dump(front_out, allow_unicode=True, sort_keys=False).strip()
        return f"---\n{rendered_front}\n---\n\n{(body or '').lstrip()}"

    # If the draft has no front matter, inject minimal metadata so category persists.
    rendered_front = yaml.safe_dump({"category": selected_category}, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{rendered_front}\n---\n\n{(suggestion_text or '').lstrip()}"


def _insert_activity(
    conn,
    *,
    activity_type: str,
    title: str,
    description: str,
    user: str = "System",
    time_label: str = "nå",
) -> None:
    conn.execute(
        """
        INSERT INTO activities (id, type, title, description, user, time, document_id)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (str(uuid.uuid4()), activity_type, title, description, user, time_label),
    )


def _generate_suggestion_async(
    suggestion_id: str,
    original_filename: str,
    processed_text: str,
    selected_category: str | None = None,
) -> None:
    """Generate revised suggestion in background and update the existing row."""

    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE suggestions
                SET generation_status = ?,
                    generation_started_at = COALESCE(generation_started_at, datetime('now')),
                    generation_error = NULL,
                    generation_reason = NULL,
                    generation_attempts = COALESCE(generation_attempts, 0) + 1
                WHERE suggestion_id = ?
                """,
                ("running", suggestion_id),
            )
    except Exception:
        logger.exception("Failed to mark suggestion generation as running for %s", suggestion_id)

    suggestion_text: str
    fallback_used = 1
    generation_reason: str | None = None
    generation_error: str | None = None

    try:
        suggestion_text, diag = generate_revised_suggestion(
            agent=agent,
            original_filename=original_filename,
            extracted_text=processed_text,
            llm_options={},
        )
        suggestion_text = _apply_selected_category(suggestion_text, selected_category)
        fallback_used = int(bool(diag.get("fallback_used")))
        generation_reason = diag.get("reason")
        generation_error = diag.get("error")
    except Exception as exc:
        logger.exception("Background suggestion generation failed for %s", suggestion_id)
        suggestion_text = fallback_structured_document_short(original_filename, processed_text)
        suggestion_text = _apply_selected_category(suggestion_text, selected_category)
        fallback_used = 1
        generation_reason = generation_reason or f"exception:{type(exc).__name__}"
        generation_error = f"exception_in_generation:{type(exc).__name__}:{exc}"

    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE suggestions
                SET suggestion_json = ?,
                    model = ?,
                    prompt_version = ?,
                    generation_status = ?,
                    generation_fallback_used = ?,
                    generation_finished_at = datetime('now'),
                    generation_reason = COALESCE(?, generation_reason),
                    generation_error = COALESCE(?, generation_error)
                WHERE suggestion_id = ?
                """,
                (
                    suggestion_text,
                    llm_provider.model,
                    _STRUCTURING_PROMPT_VERSION,
                    "failed" if generation_error else "succeeded",
                    int(bool(fallback_used)),
                    generation_reason,
                    generation_error,
                    suggestion_id,
                ),
            )
            if not generation_error:
                _insert_activity(
                    conn,
                    activity_type="ai_suggestion",
                    title="KI-forslag klar",
                    description=original_filename,
                )
    except Exception:
        logger.exception("Failed to persist background suggestion for %s", suggestion_id)


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    upload_id = str(uuid.uuid4())
    original_filename = file.filename
    safe_filename = _sanitize_filename(original_filename)
    content_sha256 = _sha256_bytes(content)

    guessed_type, _ = mimetypes.guess_type(original_filename)
    content_type = file.content_type
    if not content_type or content_type == "application/octet-stream":
        content_type = guessed_type or "application/octet-stream"

    repo_root = get_repo_root()
    uploads_root = repo_root / "databases" / "data" / "uploads" / upload_id
    uploads_root.mkdir(parents=True, exist_ok=True)
    stored_path = uploads_root / safe_filename
    stored_path.write_bytes(content)

    try:
        processed_text = parse_document(original_filename, content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    extracted_is_empty = is_effectively_empty(processed_text)
    selected_category = _normalize_selected_category(category)

    normalized_id = str(uuid.uuid4())
    normalized_sha256 = _sha256_text(processed_text)
    suggestion_id = str(uuid.uuid4())

    fallback_suggestion = (
        unreadable_pdf_message(original_filename)
        if extracted_is_empty
        else fallback_structured_document_short(original_filename, processed_text)
    )
    fallback_suggestion = _apply_selected_category(fallback_suggestion, selected_category)

    initial_model = (llm_provider.model or "").strip() or None
    generation_status = "queued" if not extracted_is_empty else "skipped"
    generation_fallback_used = 1  # upload always returns a fallback draft first
    generation_reason = None if not extracted_is_empty else "no_extractable_text"

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
                    content_type,
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
                INSERT INTO suggestions (
                    suggestion_id,
                    upload_id,
                    suggestion_json,
                    model,
                    prompt_version,
                    status,
                    generation_status,
                    generation_fallback_used,
                    generation_attempts,
                    generation_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    suggestion_id,
                    upload_id,
                    fallback_suggestion,
                    initial_model,
                    _STRUCTURING_PROMPT_VERSION,
                    "draft",
                    generation_status,
                    generation_fallback_used,
                    0,
                    generation_reason,
                ),
            )
            _insert_activity(
                conn,
                activity_type="document_uploaded",
                title="Dokument lastet opp",
                description=original_filename,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist workflow data: {exc}")

    if not extracted_is_empty:
        background_tasks.add_task(
            _generate_suggestion_async,
            suggestion_id,
            original_filename,
            processed_text,
            selected_category,
        )

    processing = not extracted_is_empty

    return {
        "upload_id": upload_id,
        "suggestion_id": suggestion_id,
        "structured_draft": fallback_suggestion,
        "suggestion_addon": "",
        "suggestions": fallback_suggestion,
        "status": "draft",
        "model": initial_model,
        "prompt_version": _STRUCTURING_PROMPT_VERSION,
        "processing": processing,
        "llm_fallback_used": True,
        "llm_error": "Background generation in progress" if processing else "No extractable text; skipped background generation",
        "generation_status": generation_status,
        "generation_fallback_used": generation_fallback_used,
        "generation_attempts": 0,
        "generation_reason": generation_reason,
    }
