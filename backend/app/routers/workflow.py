from __future__ import annotations

import logging
import threading
import uuid
from typing import Literal, Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
import yaml
from yaml import YAMLError

from app.workflow_db.db import get_connection
from app.vector_store.config import _repo_root_from_here
from app.vector_store.config import load_vector_store_config
from app.vector_store.chroma_store import ChromaVectorStore
from app.vector_store.kb_indexer import index_kb
from app.vector_store.ollama_embeddings import OllamaEmbeddingClient


router = APIRouter(prefix="/workflow", tags=["workflow"])

logger = logging.getLogger(__name__)
_reindex_lock = threading.Lock()


def _reindex_kb_to_chroma() -> None:
    """Re-index the KB raw markdown into Chroma.

    Runs best-effort; errors are logged and do not affect the apply response.
    """

    if not _reindex_lock.acquire(blocking=False):
        logger.info("KB re-index already in progress; skipping duplicate request")
        return

    try:
        cfg = load_vector_store_config()
        store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
        embedder = OllamaEmbeddingClient(base_url=cfg.ollama_base_url, model=cfg.ollama_embed_model)

        try:
            stats = index_kb(store=store, embedder=embedder)
            logger.info(
                "KB re-index completed: files=%s chunks=%s persist_dir=%s",
                stats.get("files"),
                stats.get("chunks"),
                str(cfg.persist_dir),
            )
        except Exception:
            logger.exception("KB re-index failed")
    finally:
        _reindex_lock.release()


def _external_status(db_status: str) -> str:
    # Keep API wording aligned with the upload endpoint response.
    if db_status == "draft":
        return "pending_approval"
    return db_status


def _split_front_matter(doc: str) -> tuple[dict, str]:
    """Parse YAML front matter if present.

    Expected format:
    ---\n<yaml>\n---\n<body>

    This function is defensive because LLM-generated YAML may be slightly invalid
    (e.g., unquoted ':' in scalar values). We attempt a small repair for common
    issues; if parsing still fails, we treat it as no front matter.
    """

    text = doc.lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}, doc

    # Find the closing '---' line.
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

    def parse(raw: str) -> dict:
        parsed = yaml.safe_load(raw) or {}
        return parsed if isinstance(parsed, dict) else {}

    try:
        return parse(front_raw), body
    except YAMLError:
        # Minimal repair: quote title values that contain ':' (common YAML pitfall).
        repaired_lines = []
        for line in front_raw.splitlines():
            if line.startswith("title:"):
                value = line[len("title:") :].strip()
                if value and not (value.startswith("\"") or value.startswith("'")) and ":" in value:
                    safe = value.replace("\\", "\\\\").replace("\"", "\\\"")
                    repaired_lines.append(f'title: "{safe}"')
                    continue
            repaired_lines.append(line)
        repaired = "\n".join(repaired_lines) + ("\n" if front_raw.endswith("\n") else "")

        try:
            return parse(repaired), body
        except YAMLError:
            return {}, doc


def _slugify(value: str) -> str:
    v = (value or "").strip().lower()
    out = []
    prev_dash = False
    for ch in v:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                out.append("-")
                prev_dash = True
    slug = "".join(out).strip("-")
    return slug or "kb-entry"


def _kb_raw_root() -> "Path":
    repo_root = _repo_root_from_here()
    return Path(repo_root) / "databases" / "knowledge_base" / "raw"


def _resolve_kb_path(kb_path: str) -> "Path":
    """Resolve a user-provided kb path safely under the KB raw root."""
    root = _kb_raw_root().resolve()
    rel = Path(kb_path)
    rel = Path(*rel.parts)  # normalize
    if rel.is_absolute():
        raise ValueError("kb_path must be relative")

    full = (root / rel).resolve()
    if root not in full.parents and full != root:
        raise ValueError("kb_path escapes KB root")
    if full.suffix.lower() != ".md":
        raise ValueError("kb_path must end with .md")
    return full


def _next_available_kb_path(base_name: str, suggestion_id: str) -> "Path":
    """Return an available KB path under raw/, avoiding collisions."""
    candidate = _resolve_kb_path(f"{base_name}.md")
    if not candidate.exists():
        return candidate

    suffixes = [suggestion_id[:8]]
    suffixes.extend(str(i) for i in range(2, 1000))
    for suffix in suffixes:
        candidate = _resolve_kb_path(f"{base_name}-{suffix}.md")
        if not candidate.exists():
            return candidate

    raise HTTPException(status_code=409, detail="Could not allocate unique KB file path")


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


class SuggestionListItem(BaseModel):
    suggestion_id: str
    upload_id: str
    status: str
    created_at: str
    original_filename: Optional[str] = None


class ApplyRequest(BaseModel):
    kb_path: Optional[str] = Field(
        default=None,
        description="Relative path under databases/knowledge_base/raw/ (e.g., 'procedures/pump-a.md'). If omitted, a name is derived from YAML 'id' or 'title'.",
    )
    notes: Optional[str] = None


@router.get("/suggestions", response_model=list[SuggestionListItem])
def list_suggestions(limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)) -> list[SuggestionListItem]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.suggestion_id, s.upload_id, s.status, s.created_at, u.original_filename
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
        )
        for row in rows
    ]


class ApplyResponse(BaseModel):
    suggestion_id: str
    kb_path: str
    change_id: str
    status: Literal["applied"]
    reindex: Literal["scheduled"]


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion(suggestion_id: str) -> SuggestionResponse:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT suggestion_id, upload_id, status, model, prompt_version, suggestion_json, created_at
            FROM suggestions
            WHERE suggestion_id = ?
            """,
            (suggestion_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return SuggestionResponse(
        suggestion_id=row["suggestion_id"],
        upload_id=row["upload_id"],
        status=_external_status(row["status"]),
        model=row["model"],
        prompt_version=row["prompt_version"],
        suggestion_json=row["suggestion_json"],
        created_at=row["created_at"],
    )


@router.post("/suggestions/{suggestion_id}/review", response_model=ReviewResponse)
def review_suggestion(suggestion_id: str, request: ReviewRequest) -> ReviewResponse:
    review_id = str(uuid.uuid4())

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT suggestion_id, status FROM suggestions WHERE suggestion_id = ?",
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
            (review_id, suggestion_id, request.reviewer, request.decision, request.comment),
        )

        conn.execute(
            "UPDATE suggestions SET status = ? WHERE suggestion_id = ?",
            (request.decision, suggestion_id),
        )

    return ReviewResponse(
        suggestion_id=suggestion_id,
        review_id=review_id,
        status=request.decision,
    )


@router.post("/suggestions/{suggestion_id}/apply", response_model=ApplyResponse)
def apply_suggestion(suggestion_id: str, request: ApplyRequest, background_tasks: BackgroundTasks) -> ApplyResponse:
    """Apply an approved suggestion to the KB (write Markdown file + record audit row)."""

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

    # Write the suggestion as-is (YAML front matter + Markdown body).
    kb_file.write_text(suggestion_text.rstrip() + "\n", encoding="utf-8")

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
            "UPDATE suggestions SET status = ?, target_kb_path = ? WHERE suggestion_id = ?",
            ("applied", kb_file.as_posix(), suggestion_id),
        )

    # Automatically refresh the vector index after applying KB changes.
    background_tasks.add_task(_reindex_kb_to_chroma)

    return ApplyResponse(
        suggestion_id=suggestion_id,
        kb_path=kb_file.as_posix(),
        change_id=change_id,
        status="applied",
        reindex="scheduled",
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
