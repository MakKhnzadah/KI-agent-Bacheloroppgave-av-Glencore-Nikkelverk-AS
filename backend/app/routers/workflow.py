from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import yaml
from yaml import YAMLError

from app.workflow_db.db import get_connection
from app.vector_store.config import _repo_root_from_here
from app.vector_store.config import load_vector_store_config
from app.kb.kb_reader import get_kb_doc, kb_stats
from app.routers.workflow_helpers import (
    _api_error,
    _external_status,
    _iter_kb_markdown_files,
    _kb_raw_root,
    _looks_like_non_norwegian,
    _mark_reindex_scheduled,
    _next_available_kb_path,
    _read_text_best_effort,
    _reindex_kb_to_chroma,
    _require_authenticated_user,
    _require_expert_user,
    _resolve_kb_path,
    _shingles,
    _similarity_metrics,
    _slugify,
    _split_front_matter,
    _tokenize_for_similarity,
    get_reindex_status_snapshot,
)


router = APIRouter(prefix="/workflow", tags=["workflow"])

logger = logging.getLogger(__name__)
_STRUCTURING_PROMPT_VERSION = os.getenv("STRUCTURING_PROMPT_VERSION", "2026-04-14-rs4").strip() or "2026-04-14-rs4"

_fallback_regen_lock = threading.Lock()
_fallback_regen_inflight: set[str] = set()


def _insert_activity(
    conn,
    *,
    activity_type: str,
    title: str,
    description: str,
    user: str,
    time_label: str = "nå",
) -> None:
    conn.execute(
        """
        INSERT INTO activities (id, type, title, description, user, time, document_id)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (str(uuid.uuid4()), activity_type, title, description, user, time_label),
    )


def _ensure_kb_issue_reports_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS kb_issue_reports (
            report_id TEXT PRIMARY KEY,
            kb_path TEXT NOT NULL,
            message TEXT NOT NULL,
            document_title TEXT,
            context_excerpt TEXT,
            reported_by TEXT NOT NULL,
            reported_role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kb_issue_reports_kb_path
        ON kb_issue_reports(kb_path)
        """
    )


class KbIssueReportRequest(BaseModel):
    kb_path: str
    message: str = Field(..., min_length=5, max_length=4000)
    document_title: Optional[str] = None
    context_excerpt: Optional[str] = None


class KbIssueReportResponse(BaseModel):
    report_id: str
    kb_path: str
    status: Literal["submitted"]
    reported_by: str
    reported_role: str
    created_at: str


class SimilarityMatch(BaseModel):
    kb_path: str
    title: Optional[str] = None
    jaccard: float = Field(..., ge=0.0, le=1.0)
    coverage_new: float = Field(..., ge=0.0, le=1.0)
    coverage_existing: float = Field(..., ge=0.0, le=1.0)


class SimilarityResponse(BaseModel):
    suggestion_id: str
    matches: list[SimilarityMatch]


class SimilarityCheckRequest(BaseModel):
    document: str


class SimilarityCheckResponse(BaseModel):
    matches: list[SimilarityMatch]


class KbStatsResponse(BaseModel):
    total: int
    by_category: dict[str, int]


class KbDocumentResponse(BaseModel):
    id: str
    kb_path: str
    title: str
    author: str
    date: str
    category: str
    content: str

class KbDocumentListItem(BaseModel):
    kb_path: str
    title: str
    author: str
    date: str
    category: str

class KbDocumentsListResponse(BaseModel):
    total: int
    returned: int
    offset: int
    limit: int
    documents: list[KbDocumentListItem]


class KbDeleteResponse(BaseModel):
    status: str
    deleted_kb_path: str
    deleted_indexed: bool
    indexed_delete_error: Optional[str] = None


class ReindexStatusResponse(BaseModel):
    state: str
    current_run_id: Optional[str] = None
    last_completed_run_id: Optional[str] = None
    last_reason: Optional[str] = None
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_error: Optional[str] = None
    last_indexed_files: Optional[int] = None
    last_indexed_chunks: Optional[int] = None


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: Optional[str] = None
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    suggestion_id: str
    review_id: str
    status: Literal["approved", "rejected"]


class SuggestionResponse(BaseModel):
    suggestion_id: str
    upload_id: str
    status: str
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    suggestion_json: str = Field(..., description="Structured document returned by the agent (YAML front matter + Markdown)")
    created_at: str
    generation_status: Optional[str] = None
    generation_fallback_used: Optional[int] = None
    generation_attempts: Optional[int] = None
    generation_started_at: Optional[str] = None
    generation_finished_at: Optional[str] = None
    generation_reason: Optional[str] = None
    generation_error: Optional[str] = None


def _schedule_fallback_regeneration(*, suggestion_id: str, upload_id: str, original_filename: str) -> None:
    with _fallback_regen_lock:
        # Throttle: regenerating a suggestion is expensive (LLM call). The frontend may fetch
        # many suggestions in parallel on page load, so we keep this strictly bounded.
        if len(_fallback_regen_inflight) >= 1:
            return
        if suggestion_id in _fallback_regen_inflight:
            return
        _fallback_regen_inflight.add(suggestion_id)

    # Run as a daemon thread so server shutdown is not blocked by long LLM calls.
    thread = threading.Thread(
        target=_regenerate_suggestion_in_background,
        args=(suggestion_id, upload_id, original_filename),
        name=f"regen-{suggestion_id[:8]}",
        daemon=True,
    )
    thread.start()


def _regenerate_suggestion_in_background(suggestion_id: str, upload_id: str, original_filename: str) -> None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT text
                FROM normalized_documents
                WHERE upload_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (upload_id,),
            ).fetchone()
        if row is None:
            return

        processed_text = (row["text"] or "").strip()
        # Mirror upload-time threshold (best-effort guard).
        if len(re.findall(r"\b\w+\b", processed_text)) < 40:
            return

        # Reuse the same structuring pipeline used by /documents/upload.
        from app.routers.documents import _generate_suggestion_async  # local import avoids import cycles

        _generate_suggestion_async(suggestion_id, original_filename, processed_text)
    finally:
        with _fallback_regen_lock:
            _fallback_regen_inflight.discard(suggestion_id)


class SuggestionListItem(BaseModel):
    suggestion_id: str
    upload_id: str
    status: str
    created_at: str
    original_filename: Optional[str] = None
    generation_status: Optional[str] = None
    generation_fallback_used: Optional[int] = None


class OriginalDocumentResponse(BaseModel):
    suggestion_id: str
    upload_id: str
    original_filename: Optional[str] = None
    text: str


class ApplyRequest(BaseModel):
    kb_path: Optional[str] = Field(
        default=None,
        description="Relative path under databases/knowledge_base/raw/ (e.g., 'procedures/pump-a.md'). If omitted, a name is derived from YAML 'id' or 'title'.",
    )
    notes: Optional[str] = None


class SuggestionUpdateRequest(BaseModel):
    suggestion_json: str = Field(..., description="Updated structured draft (YAML front matter + Markdown)")


@router.get("/suggestions", response_model=list[SuggestionListItem])
def list_suggestions(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> list[SuggestionListItem]:
    _require_expert_user(authorization)

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.suggestion_id,
                   s.upload_id,
                   s.status,
                   s.created_at,
                   s.generation_status,
                   s.generation_fallback_used,
                   u.original_filename
            FROM suggestions s
            LEFT JOIN uploads u ON u.upload_id = s.upload_id
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    return [
        SuggestionListItem(
            suggestion_id=row["suggestion_id"],
            upload_id=row["upload_id"],
            status=_external_status(row["status"]),
            created_at=row["created_at"],
            original_filename=row["original_filename"],
            generation_status=row["generation_status"],
            generation_fallback_used=row["generation_fallback_used"],
        )
        for row in rows
    ]


class ApplyResponse(BaseModel):
    suggestion_id: str
    kb_path: str
    change_id: str
    status: Literal["applied"]
    reindex: Literal["scheduled"]
    reindex_run_id: str


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion(
    suggestion_id: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> SuggestionResponse:
    _require_expert_user(authorization)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT suggestion_id,
                   upload_id,
                   status,
                   model,
                   prompt_version,
                   suggestion_json,
                   created_at,
                   generation_status,
                   generation_fallback_used,
                   generation_attempts,
                   generation_started_at,
                   generation_finished_at,
                   generation_reason,
                   generation_error
            FROM suggestions
            WHERE suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion_json = row["suggestion_json"] or ""
    model = (row["model"] or "").strip()
    prompt_version = (row["prompt_version"] or "").strip()
    generation_status = (row["generation_status"] or "").strip()
    # One-time auto-regeneration:
    # - Old fallback drafts (classic marker)
    # - Old-format drafts lacking evidence markers (KILDE)
    # - Outputs that are clearly non-Norwegian
    # This lets already-uploaded documents benefit from improved structuring logic.
    needs_regen = False
    if "- Automatisk fallback: KI klarte ikke å levere gyldig strukturert output." in suggestion_json:
        needs_regen = True
    if "(KILDE: \"" not in suggestion_json:
        # Old suggestions were not evidence-backed.
        needs_regen = True
    if _looks_like_non_norwegian(suggestion_json):
        needs_regen = True

    if (
        needs_regen
        and generation_status not in {"queued", "running"}
        and row["upload_id"]
        and prompt_version != _STRUCTURING_PROMPT_VERSION
    ):
        try:
            # original_filename is needed for title derivation; fetch best-effort.
            with get_connection() as conn:
                urow = conn.execute(
                    "SELECT original_filename FROM uploads WHERE upload_id = ?",
                    (row["upload_id"],),
                ).fetchone()
            original_filename = (urow["original_filename"] if urow else None) or "document"
            _schedule_fallback_regeneration(
                suggestion_id=suggestion_id,
                upload_id=row["upload_id"],
                original_filename=original_filename,
            )
        except Exception:
            logger.exception("Failed to schedule fallback regeneration for %s", suggestion_id)

    return SuggestionResponse(
        suggestion_id=row["suggestion_id"],
        upload_id=row["upload_id"],
        status=_external_status(row["status"]),
        model=row["model"],
        prompt_version=row["prompt_version"],
        suggestion_json=suggestion_json,
        created_at=row["created_at"],
        generation_status=row["generation_status"],
        generation_fallback_used=row["generation_fallback_used"],
        generation_attempts=row["generation_attempts"],
        generation_started_at=row["generation_started_at"],
        generation_finished_at=row["generation_finished_at"],
        generation_reason=row["generation_reason"],
        generation_error=row["generation_error"],
    )


@router.patch("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def update_suggestion(
    suggestion_id: str,
    request: SuggestionUpdateRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> SuggestionResponse:
    """Persist manual edits to a suggestion draft before review/apply."""

    _require_expert_user(authorization)

    updated = (request.suggestion_json or "").strip()
    if not updated:
        raise HTTPException(status_code=400, detail="suggestion_json cannot be empty")

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT suggestion_id,
                   upload_id,
                   status,
                   model,
                   prompt_version,
                   suggestion_json,
                   created_at,
                   generation_status,
                   generation_fallback_used,
                   generation_attempts,
                   generation_started_at,
                   generation_finished_at,
                   generation_reason,
                   generation_error
            FROM suggestions
            WHERE suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        if row["status"] not in {"draft", "rejected"}:
            raise HTTPException(
                status_code=409,
                detail=f"Suggestion cannot be edited in status '{_external_status(row['status'])}'",
            )

        conn.execute(
            "UPDATE suggestions SET suggestion_json = ? WHERE suggestion_id = ?",
            (updated, suggestion_id),
        )

    return SuggestionResponse(
        suggestion_id=row["suggestion_id"],
        upload_id=row["upload_id"],
        status=_external_status(row["status"]),
        model=row["model"],
        prompt_version=row["prompt_version"],
        suggestion_json=updated,
        created_at=row["created_at"],
        generation_status=row["generation_status"],
        generation_fallback_used=row["generation_fallback_used"],
        generation_attempts=row["generation_attempts"],
        generation_started_at=row["generation_started_at"],
        generation_finished_at=row["generation_finished_at"],
        generation_reason=row["generation_reason"],
        generation_error=row["generation_error"],
    )


@router.get("/suggestions/{suggestion_id}/similarity", response_model=SimilarityResponse)
def get_suggestion_similarity(
    suggestion_id: str,
    limit: int = Query(5, ge=1, le=20),
    min_coverage_new: float = Query(0.0, ge=0.0, le=1.0),
    exclude_kb_path: Optional[str] = Query(
        default=None,
        description="Optional relative path under databases/knowledge_base/raw to exclude from matching.",
    ),
) -> SimilarityResponse:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT suggestion_id, suggestion_json
            FROM suggestions
            WHERE suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion_json = row["suggestion_json"] or ""
    suggestion_front, suggestion_body = _split_front_matter(suggestion_json)
    suggestion_title = suggestion_front.get("title") if isinstance(suggestion_front, dict) else None

    new_text = (str(suggestion_title) + "\n\n" if suggestion_title else "") + (suggestion_body or "")
    new_tokens = _tokenize_for_similarity(new_text)
    new_set = _shingles(new_tokens)

    kb_root = _kb_raw_root()
    kb_files = _iter_kb_markdown_files()
    if exclude_kb_path:
        try:
            excluded_full = _resolve_kb_path(exclude_kb_path)
        except Exception:
            raise HTTPException(status_code=400, detail="exclude_kb_path is invalid")
        kb_files = [p for p in kb_files if p.resolve() != excluded_full.resolve()]

    if not new_set or not kb_files:
        return SimilarityResponse(suggestion_id=suggestion_id, matches=[])

    matches: list[SimilarityMatch] = []
    for p in kb_files:
        try:
            existing_raw = _read_text_best_effort(p)
        except OSError:
            continue

        front, body = _split_front_matter(existing_raw)
        title = None
        if isinstance(front, dict):
            maybe_title = front.get("title") or front.get("id")
            if isinstance(maybe_title, str) and maybe_title.strip():
                title = maybe_title.strip()

        existing_text = (title + "\n\n" if title else "") + (body or "")
        existing_tokens = _tokenize_for_similarity(existing_text)
        existing_set = _shingles(existing_tokens)
        if not existing_set:
            continue

        inter = len(new_set & existing_set)
        if inter == 0:
            continue

        union = len(new_set | existing_set)
        jaccard = inter / union if union else 0.0
        coverage_new = inter / len(new_set) if new_set else 0.0
        coverage_existing = inter / len(existing_set) if existing_set else 0.0

        if coverage_new < min_coverage_new:
            continue

        rel = p.resolve().relative_to(kb_root.resolve())
        matches.append(
            SimilarityMatch(
                kb_path=rel.as_posix(),
                title=title,
                jaccard=jaccard,
                coverage_new=coverage_new,
                coverage_existing=coverage_existing,
            )
        )

    matches.sort(key=lambda m: (m.coverage_new, m.jaccard, m.kb_path), reverse=True)
    return SimilarityResponse(suggestion_id=suggestion_id, matches=matches[:limit])


@router.post("/similarity-check", response_model=SimilarityCheckResponse)
def check_similarity_for_document(
    request: SimilarityCheckRequest,
    limit: int = Query(5, ge=1, le=20),
    min_coverage_new: float = Query(0.0, ge=0.0, le=1.0),
    exclude_kb_path: Optional[str] = Query(
        default=None,
        description="Optional relative path under databases/knowledge_base/raw to exclude from matching.",
    ),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> SimilarityCheckResponse:
    """Check similarity for an arbitrary Markdown document (not necessarily stored as a suggestion).

    This is useful for iterative editing in the UI: the user can revise a draft and re-check overlap
    against the knowledge base without persisting the draft to the workflow DB.
    """

    _require_expert_user(authorization)

    doc = request.document or ""
    front, body = _split_front_matter(doc)
    title = front.get("title") if isinstance(front, dict) else None
    new_text = (str(title) + "\n\n" if title else "") + (body or "")

    new_tokens = _tokenize_for_similarity(new_text)
    new_set = _shingles(new_tokens)

    kb_root = _kb_raw_root()
    kb_files = _iter_kb_markdown_files()
    if exclude_kb_path:
        try:
            excluded_full = _resolve_kb_path(exclude_kb_path)
        except Exception:
            raise HTTPException(status_code=400, detail="exclude_kb_path is invalid")
        kb_files = [p for p in kb_files if p.resolve() != excluded_full.resolve()]

    if not new_set or not kb_files:
        return SimilarityCheckResponse(matches=[])

    matches: list[SimilarityMatch] = []
    for p in kb_files:
        try:
            existing_raw = _read_text_best_effort(p)
        except OSError:
            continue

        existing_front, existing_body = _split_front_matter(existing_raw)
        existing_title = None
        if isinstance(existing_front, dict):
            maybe_title = existing_front.get("title") or existing_front.get("id")
            if isinstance(maybe_title, str) and maybe_title.strip():
                existing_title = maybe_title.strip()

        existing_text = (existing_title + "\n\n" if existing_title else "") + (existing_body or "")
        existing_tokens = _tokenize_for_similarity(existing_text)
        existing_set = _shingles(existing_tokens)
        if not existing_set:
            continue

        inter = len(new_set & existing_set)
        if inter == 0:
            continue

        union = len(new_set | existing_set)
        jaccard = inter / union if union else 0.0
        coverage_new = inter / len(new_set) if new_set else 0.0
        coverage_existing = inter / len(existing_set) if existing_set else 0.0

        if coverage_new < min_coverage_new:
            continue

        rel = p.resolve().relative_to(kb_root.resolve())
        matches.append(
            SimilarityMatch(
                kb_path=rel.as_posix(),
                title=existing_title,
                jaccard=jaccard,
                coverage_new=coverage_new,
                coverage_existing=coverage_existing,
            )
        )

    matches.sort(key=lambda m: (m.coverage_new, m.jaccard, m.kb_path), reverse=True)
    return SimilarityCheckResponse(matches=matches[:limit])


@router.get("/kb/stats", response_model=KbStatsResponse)
def get_kb_stats(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> KbStatsResponse:
    _require_authenticated_user(authorization, allowed_roles={"employee", "expert", "admin"})

    total, by_cat = kb_stats()
    return KbStatsResponse(total=total, by_category=by_cat)


@router.get("/kb/reindex-status", response_model=ReindexStatusResponse)
def get_kb_reindex_status(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> ReindexStatusResponse:
    _require_expert_user(authorization)

    snapshot = get_reindex_status_snapshot()
    return ReindexStatusResponse(**snapshot)


@router.get("/kb/document", response_model=KbDocumentResponse)
def get_kb_document(
    kb_path: str = Query(..., description="Relative path under databases/knowledge_base/raw (e.g. 'procedures/pump-a.md')."),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> KbDocumentResponse:
    _require_authenticated_user(authorization, allowed_roles={"employee", "expert", "admin"})

    try:
        doc = get_kb_doc(kb_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="kb_path is invalid")
    except OSError:
        raise HTTPException(status_code=404, detail="KB document not found")

    return KbDocumentResponse(
        id=doc.kb_path,
        kb_path=doc.kb_path,
        title=doc.title,
        author=doc.author,
        date=doc.date,
        category=doc.category,
        content=doc.content,
    )

@router.get("/kb/documents", response_model=KbDocumentsListResponse)
def list_kb_documents(
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = Query(default=None, description="Optional category filter. Use 'All' or omit for no filtering."),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> KbDocumentsListResponse:
    """List KB markdown documents from the raw knowledge base on disk."""

    _require_authenticated_user(authorization, allowed_roles={"employee", "expert", "admin"})

    from app.kb.kb_reader import iter_kb_markdown_files, doc_metadata, read_text_best_effort, kb_raw_root

    wanted = (category or "").strip()
    wanted_norm = wanted if wanted and wanted != "All" else ""

    root = kb_raw_root().resolve()
    docs: list[KbDocumentListItem] = []

    for p in iter_kb_markdown_files():
        try:
            raw = read_text_best_effort(p, max_chars=60_000)
        except OSError:
            continue

        rel = p.resolve().relative_to(root).as_posix()
        title, cat, author, date = doc_metadata(raw, kb_path=rel)
        if wanted_norm and cat != wanted_norm:
            continue

        docs.append(
            KbDocumentListItem(
                kb_path=rel,
                title=title,
                author=author,
                date=date,
                category=cat,
            )
        )

    docs.sort(key=lambda d: ((d.title or "").lower(), (d.kb_path or "").lower()))
    total = len(docs)
    sliced = docs[offset : offset + limit]
    return KbDocumentsListResponse(
        total=total,
        returned=len(sliced),
        offset=offset,
        limit=limit,
        documents=sliced,
    )


@router.post("/kb/issues", response_model=KbIssueReportResponse)
def report_kb_issue(
    payload: KbIssueReportRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> KbIssueReportResponse:
    reported_by, reported_role = _require_authenticated_user(
        authorization,
        allowed_roles={"employee", "expert", "admin"},
    )

    report_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    kb_path = (payload.kb_path or "").strip()
    if not kb_path:
        raise HTTPException(status_code=400, detail="kb_path is required")

    with get_connection() as conn:
        _ensure_kb_issue_reports_table(conn)
        conn.execute(
            """
            INSERT INTO kb_issue_reports (
                report_id,
                kb_path,
                message,
                document_title,
                context_excerpt,
                reported_by,
                reported_role,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
            """,
            (
                report_id,
                kb_path,
                payload.message.strip(),
                (payload.document_title or "").strip() or None,
                (payload.context_excerpt or "").strip() or None,
                reported_by,
                reported_role,
                created_at,
            ),
        )

    return KbIssueReportResponse(
        report_id=report_id,
        kb_path=kb_path,
        status="submitted",
        reported_by=reported_by,
        reported_role=reported_role,
        created_at=created_at,
    )


@router.delete("/kb/documents", response_model=KbDeleteResponse)
def delete_kb_document(
    kb_path: str = Query(..., description="Relative path under databases/knowledge_base/raw (e.g. 'procedures/pump-a.md')."),
    delete_indexed: bool = Query(default=True, description="Also remove indexed chunks from vector DB when possible."),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> KbDeleteResponse:
    """Delete a raw KB markdown document (pre-index source file)."""

    _require_expert_user(authorization)

    try:
        from app.kb.kb_reader import kb_raw_root, resolve_kb_path

        full = resolve_kb_path(kb_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="kb_path is invalid")

    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="KB document not found")

    try:
        full.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete KB document: {exc}")

    # Best-effort cleanup of empty directories under KB raw root.
    try:
        root = kb_raw_root().resolve()
        parent = full.parent.resolve()
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent.resolve()
    except Exception:
        # Ignore cleanup errors; file deletion already succeeded.
        pass

    deleted_indexed = False
    indexed_delete_error: Optional[str] = None

    if delete_indexed:
        try:
            from app.vector_store.chroma_store import ChromaVectorStore
            from app.vector_store.config import load_vector_store_config

            cfg = load_vector_store_config()
            store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
            store.delete(where={"path": str(full.resolve().as_posix())})
            deleted_indexed = True
        except Exception as exc:
            indexed_delete_error = str(exc)

    return KbDeleteResponse(
        status="ok",
        deleted_kb_path=kb_path,
        deleted_indexed=deleted_indexed,
        indexed_delete_error=indexed_delete_error,
    )


@router.get("/suggestions/{suggestion_id}/original", response_model=OriginalDocumentResponse)
def get_suggestion_original(
    suggestion_id: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> OriginalDocumentResponse:
    _require_expert_user(authorization)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.suggestion_id, s.upload_id, u.original_filename, n.text
            FROM suggestions s
            LEFT JOIN uploads u ON u.upload_id = s.upload_id
            LEFT JOIN normalized_documents n ON n.upload_id = s.upload_id
            WHERE s.suggestion_id = ?
            ORDER BY n.created_at DESC
            LIMIT 1
            """,
            (suggestion_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    text = row["text"]
    if text is None:
        raise HTTPException(status_code=404, detail="Original content not found")

    return OriginalDocumentResponse(
        suggestion_id=row["suggestion_id"],
        upload_id=row["upload_id"],
        original_filename=row["original_filename"],
        text=text,
    )


@router.head("/suggestions/{suggestion_id}/file")
def head_suggestion_file(
    suggestion_id: str,
    render: Optional[str] = Query(default=None, description="Optional render mode. Use 'pdf' to request a PDF rendition for .docx files."),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Response:
    """HEAD variant for file downloads.

    Some clients (and the frontend) rely on Content-Type detection via HEAD.
    """

    _require_expert_user(authorization)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.suggestion_id, s.upload_id, u.original_filename, u.content_type, u.stored_path
            FROM suggestions s
            LEFT JOIN uploads u ON u.upload_id = s.upload_id
            WHERE s.suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    stored_path = row["stored_path"]
    if not stored_path:
        raise HTTPException(status_code=404, detail="Original file not found")

    file_path = Path(stored_path)
    original_filename = row["original_filename"] or file_path.name
    content_type = row["content_type"] or ""
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(original_filename)
        content_type = guessed_type or "application/octet-stream"

    render_mode = (render or "").strip().lower()
    if render_mode == "pdf" and original_filename.lower().endswith(".docx"):
        pdf_name = f"{Path(original_filename).stem}.pdf"
        return Response(
            status_code=status.HTTP_200_OK,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{pdf_name}"'},
        )

    return Response(
        status_code=status.HTTP_200_OK,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{original_filename}"'},
    )


@router.get("/suggestions/{suggestion_id}/file")
def get_suggestion_file(
    suggestion_id: str,
    render: Optional[str] = Query(default=None, description="Optional render mode. Use 'pdf' to request a PDF rendition for .docx files."),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> FileResponse:
    _require_expert_user(authorization)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.suggestion_id, s.upload_id, u.original_filename, u.content_type, u.stored_path
            FROM suggestions s
            LEFT JOIN uploads u ON u.upload_id = s.upload_id
            WHERE s.suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    stored_path = row["stored_path"]
    if not stored_path:
        raise HTTPException(status_code=404, detail="Original file not found")

    repo_root = Path(_repo_root_from_here())
    uploads_root = (repo_root / "databases" / "data" / "uploads").resolve()

    file_path = Path(stored_path)
    if not file_path.is_absolute():
        file_path = repo_root / file_path
    file_path = file_path.resolve()

    if uploads_root not in file_path.parents:
        raise HTTPException(status_code=400, detail="Invalid stored file path")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Original file missing on disk")

    original_filename = row["original_filename"] or file_path.name
    content_type = row["content_type"] or ""
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(original_filename)
        content_type = guessed_type or "application/octet-stream"

    render_mode = (render or "").strip().lower()
    if render_mode == "pdf" and original_filename.lower().endswith(".docx"):
        render_root = (uploads_root / ".rendered").resolve()
        render_root.mkdir(parents=True, exist_ok=True)
        cached_pdf = (render_root / f"{suggestion_id}.pdf").resolve()

        try:
            needs_render = True
            if cached_pdf.exists():
                needs_render = cached_pdf.stat().st_mtime < file_path.stat().st_mtime

            if needs_render:
                _render_docx_to_pdf(file_path, cached_pdf)
        except Exception as exc:
            # Never fail the request: fall back to a readable text-based PDF.
            logger.warning("DOCX->PDF conversion failed for %s: %s", suggestion_id, exc)
            extracted_text: str | None = None
            try:
                with get_connection() as conn:
                    trow = conn.execute(
                        """
                        SELECT text
                        FROM normalized_documents
                        WHERE upload_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (row["upload_id"],),
                    ).fetchone()
                if trow is not None:
                    extracted_text = trow["text"]
            except Exception:
                extracted_text = None

            _render_text_to_pdf(
                extracted_text
                or f"(Kunne ikke konvertere Word-dokumentet til PDF med layout. Viser tekstutdrag.)\n\nFil: {original_filename}\n",
                cached_pdf,
            )

        pdf_name = f"{Path(original_filename).stem}.pdf"
        return FileResponse(
            path=str(cached_pdf),
            media_type="application/pdf",
            filename=pdf_name,
            headers={"Content-Disposition": f'inline; filename="{pdf_name}"'},
        )

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=original_filename,
        headers={"Content-Disposition": f'inline; filename="{original_filename}"'},
    )


def _render_text_to_pdf(text: str, pdf_path: Path) -> None:
    """Render plain text into a simple, readable PDF.

    Used as a last-resort fallback when DOCX conversion isn't available.
    """

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    from fpdf import FPDF  # fpdf2

    def normalize(s: str) -> str:
        s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
        s = s.replace("\u2013", "-").replace("\u2014", "-")
        s = s.replace("\u2018", "'").replace("\u2019", "'")
        s = s.replace("\u201C", '"').replace("\u201D", '"')
        s = s.replace("\u2022", "-")
        return s.encode("latin-1", errors="replace").decode("latin-1")

    def soft_wrap_unbreakable_tokens(s: str, max_token: int = 60) -> str:
        # fpdf2 can throw if a single token is wider than the available cell width.
        # Insert spaces into long tokens (URLs/IDs) so wrapping becomes possible.
        parts = re.split(r"(\s+)", s)
        out: list[str] = []
        for p in parts:
            if not p or p.isspace():
                out.append(p)
                continue
            if len(p) <= max_token:
                out.append(p)
                continue
            out.append(" ".join(p[i : i + max_token] for i in range(0, len(p), max_token)))
        return "".join(out)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    for raw_line in (text or "").replace("\r\n", "\n").split("\n"):
        line = normalize(raw_line).rstrip()
        if not line.strip():
            pdf.ln(4)
            continue
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5.2, txt=soft_wrap_unbreakable_tokens(line))

    with tempfile.NamedTemporaryFile(
        prefix=pdf_path.stem + "-",
        suffix=".pdf",
        dir=str(pdf_path.parent),
        delete=False,
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        pdf.output(str(tmp_path))
        tmp_path.replace(pdf_path)
    finally:
        if tmp_path.exists() and tmp_path != pdf_path:
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _render_docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    """Render a PDF from DOCX, preferring high-fidelity converters.

    Priority:
    1) Microsoft Word automation (docx2pdf) on Windows (best fidelity)
    2) LibreOffice (soffice) if installed (good fidelity)
    3) Text-based fallback (fpdf2) for readability when no converter is available
    """

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="docx-render-") as tmp_dir:
        tmp = Path(tmp_dir)

        # 1) docx2pdf (Windows + Word). Output path is a directory.
        if sys.platform.startswith("win"):
            try:
                from docx2pdf import convert  # type: ignore

                convert(str(docx_path), str(tmp))
                produced = tmp / f"{docx_path.stem}.pdf"
                if produced.exists():
                    produced.replace(pdf_path)
                    return
            except Exception:
                # If Word isn't available or conversion fails, try LibreOffice next.
                pass

        # 2) LibreOffice headless conversion.
        soffice = shutil.which("soffice") or shutil.which("soffice.exe") or shutil.which("libreoffice")
        if soffice:
            cmd = [
                soffice,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(docx_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode == 0:
                produced = tmp / f"{docx_path.stem}.pdf"
                if produced.exists():
                    produced.replace(pdf_path)
                    return
            else:
                logger.warning("LibreOffice conversion failed: %s", (proc.stderr or proc.stdout or "").strip())

        # 3) Readability fallback: render DOCX text into PDF.
        from docx import Document  # python-docx
        from fpdf import FPDF  # fpdf2

        doc = Document(str(docx_path))
        paragraphs = [p.text for p in doc.paragraphs]

        def normalize(s: str) -> str:
            s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
            s = s.replace("\u2013", "-").replace("\u2014", "-")
            s = s.replace("\u2018", "'").replace("\u2019", "'")
            s = s.replace("\u201C", '"').replace("\u201D", '"')
            s = s.replace("\u2022", "-")
            return s.encode("latin-1", errors="replace").decode("latin-1")

        def soft_wrap_unbreakable_tokens(s: str, max_token: int = 60) -> str:
            parts = re.split(r"(\s+)", s)
            out: list[str] = []
            for p in parts:
                if not p or p.isspace():
                    out.append(p)
                    continue
                if len(p) <= max_token:
                    out.append(p)
                    continue
                out.append(" ".join(p[i : i + max_token] for i in range(0, len(p), max_token)))
            return "".join(out)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)

        for p in paragraphs:
            text = normalize(p).strip("\n")
            if not text.strip():
                pdf.ln(4)
                continue

            for line in text.split("\n"):
                line = line.rstrip()
                if not line:
                    pdf.ln(3)
                    continue
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 5.2, txt=soft_wrap_unbreakable_tokens(line))
            pdf.ln(2)

        with tempfile.NamedTemporaryFile(prefix=pdf_path.stem + "-", suffix=".pdf", dir=str(pdf_path.parent), delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            pdf.output(str(tmp_path))
            tmp_path.replace(pdf_path)
        finally:
            if tmp_path.exists() and tmp_path != pdf_path:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


@router.post("/suggestions/{suggestion_id}/review", response_model=ReviewResponse)
def review_suggestion(
    suggestion_id: str,
    request: ReviewRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> ReviewResponse:
    reviewer = _require_expert_user(authorization)
    review_id = str(uuid.uuid4())

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT s.suggestion_id, s.status, u.original_filename
            FROM suggestions s
            LEFT JOIN uploads u ON u.upload_id = s.upload_id
            WHERE s.suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        current_status = existing["status"]
        if current_status not in {"draft", "pending_approval"}:
            raise HTTPException(
                status_code=409,
                detail=f"Suggestion cannot be reviewed in status '{current_status}'",
            )

        conn.execute(
            """
            INSERT INTO reviews (review_id, suggestion_id, reviewer, decision, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (review_id, suggestion_id, reviewer, request.decision, request.comment),
        )

        conn.execute(
            "UPDATE suggestions SET status = ? WHERE suggestion_id = ?",
            (request.decision, suggestion_id),
        )

        description = (existing["original_filename"] or suggestion_id).strip()
        if request.decision == "approved":
            _insert_activity(
                conn,
                activity_type="document_approved",
                title="Nytt dokument godkjent",
                description=description,
                user=reviewer,
            )
        else:
            _insert_activity(
                conn,
                activity_type="document_rejected",
                title="Dokument avvist",
                description=description,
                user=reviewer,
            )

    return ReviewResponse(
        suggestion_id=suggestion_id,
        review_id=review_id,
        status=request.decision,
    )


@router.post("/suggestions/{suggestion_id}/apply", response_model=ApplyResponse)
def apply_suggestion(
    suggestion_id: str,
    request: ApplyRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> ApplyResponse:
    """Apply an approved suggestion to the KB (write Markdown file + record audit row)."""
    _require_expert_user(authorization)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT suggestion_id, upload_id, status, suggestion_json
            FROM suggestions
            WHERE suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        if row["status"] != "approved":
            raise HTTPException(
                status_code=409,
                detail=f"Suggestion must be approved before applying (current status: '{_external_status(row['status'])}')",
            )

        suggestion_text = row["suggestion_json"]

    front, body = _split_front_matter(suggestion_text)

    # Applied KB entries should not expose internal review workflow metadata.
    suggestion_text_for_kb = suggestion_text
    if front:
        front_for_kb = dict(front)
        front_for_kb.pop("review_status", None)

        rendered_front = yaml.safe_dump(front_for_kb, allow_unicode=True, sort_keys=False).strip()
        suggestion_text_for_kb = f"---\n{rendered_front}\n---\n\n{(body or '').lstrip()}"
    derived_id = str(front.get("id") or "").strip()
    derived_title = str(front.get("title") or "").strip()
    base_name = derived_id or _slugify(derived_title)

    try:
        if request.kb_path:
            kb_file = _resolve_kb_path(request.kb_path)
        else:
            kb_file = _next_available_kb_path(base_name, suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    kb_file.parent.mkdir(parents=True, exist_ok=True)

    if kb_file.exists() and request.kb_path:
        raise HTTPException(
            status_code=409,
            detail=f"KB file already exists: {kb_file.as_posix()}. Provide 'kb_path' to choose a different file.",
        )

    kb_file.write_text(suggestion_text_for_kb.rstrip() + "\n", encoding="utf-8")

    change_id = str(uuid.uuid4())

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO applied_changes (change_id, suggestion_id, kb_path, notes)
            VALUES (?, ?, ?, ?)
            """,
            (change_id, suggestion_id, kb_file.as_posix(), request.notes),
        )
        conn.execute(
            "UPDATE suggestions SET status = ?, target_kb_path = ?, suggestion_json = ? WHERE suggestion_id = ?",
            ("applied", kb_file.as_posix(), suggestion_text_for_kb, suggestion_id),
        )
        _insert_activity(
            conn,
            activity_type="system_update",
            title="Dokument publisert i kunnskapsbanken",
            description=derived_title or kb_file.name,
            user="System",
        )

    # Automatically refresh the vector index after applying KB changes.
    reindex_run_id = _mark_reindex_scheduled(reason="workflow.apply_suggestion")
    thread = threading.Thread(
        target=_reindex_kb_to_chroma,
        args=(reindex_run_id,),
        name=f"reindex-{reindex_run_id[:8]}",
        daemon=True,
    )
    thread.start()

    return ApplyResponse(
        suggestion_id=suggestion_id,
        kb_path=kb_file.as_posix(),
        change_id=change_id,
        status="applied",
        reindex="scheduled",
        reindex_run_id=reindex_run_id,
    )


@router.delete("/suggestions/{suggestion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suggestion(suggestion_id: str) -> Response:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT suggestion_id FROM suggestions WHERE suggestion_id = ?",
            (suggestion_id,),
        ).fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        conn.execute("DELETE FROM suggestions WHERE suggestion_id = ?", (suggestion_id,))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
