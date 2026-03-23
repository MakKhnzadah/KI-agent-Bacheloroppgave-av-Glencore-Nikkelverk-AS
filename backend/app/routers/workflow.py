from __future__ import annotations

import hashlib
import logging
import re
import threading
import uuid
from typing import Literal, Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import yaml
from yaml import YAMLError

from app.workflow_db.db import get_connection
from app.vector_store.config import _repo_root_from_here
from app.vector_store.config import load_vector_store_config
from app.kb.kb_reader import get_kb_doc, kb_stats


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
        try:
            from app.vector_store.chroma_store import ChromaVectorStore
            from app.vector_store.kb_indexer import index_kb
            from app.vector_store.ollama_embeddings import OllamaEmbeddingClient
        except Exception:
            logger.info("Vector search disabled (chromadb not installed); skipping KB re-index")
            return

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


_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)


def _tokenize_for_similarity(text: str, *, max_tokens: int = 6000) -> list[str]:
    tokens = _WORD_RE.findall((text or "").lower())
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
    return tokens


def _shingles(tokens: list[str], *, n: int = 5, max_shingles: int = 20000) -> set[int]:
    if n <= 0:
        raise ValueError("n must be >= 1")
    if len(tokens) < n:
        return set()

    out: set[int] = set()
    for i in range(0, len(tokens) - n + 1):
        sh = " ".join(tokens[i : i + n])
        # Stable 64-bit-ish hash (avoid Python's randomized hash())
        h = hashlib.blake2b(sh.encode("utf-8"), digest_size=8).digest()
        out.add(int.from_bytes(h, "big"))
        if len(out) >= max_shingles:
            break
    return out


def _similarity_metrics(new_text: str, existing_text: str) -> tuple[float, float, float]:
    """Return (jaccard, coverage_new, coverage_existing) in [0..1].

    coverage_new answers: "How much of the new document is already present elsewhere?"
    """

    new_tokens = _tokenize_for_similarity(new_text)
    existing_tokens = _tokenize_for_similarity(existing_text)

    new_set = _shingles(new_tokens)
    existing_set = _shingles(existing_tokens)
    if not new_set or not existing_set:
        return 0.0, 0.0, 0.0

    inter = len(new_set & existing_set)
    union = len(new_set | existing_set)
    jaccard = inter / union if union else 0.0
    coverage_new = inter / len(new_set) if new_set else 0.0
    coverage_existing = inter / len(existing_set) if existing_set else 0.0
    return jaccard, coverage_new, coverage_existing


def _iter_kb_markdown_files() -> list[Path]:
    root = _kb_raw_root()
    if not root.exists():
        return []

    files: list[Path] = []
    for p in root.rglob("*.md"):
        name = p.name.lower()
        if name in {"readme.md", "_template.md"}:
            continue
        if p.name.startswith("_"):
            continue
        files.append(p)

    files.sort(key=lambda x: str(x).lower())
    return files


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


def _read_text_best_effort(path: Path, *, max_chars: int = 300_000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars]
    return text


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
) -> SimilarityCheckResponse:
    """Check similarity for an arbitrary Markdown document (not necessarily stored as a suggestion).

    This is useful for iterative editing in the UI: the user can revise a draft and re-check overlap
    against the knowledge base without persisting the draft to the workflow DB.
    """

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
def get_kb_stats() -> KbStatsResponse:
    total, by_cat = kb_stats()
    return KbStatsResponse(total=total, by_category=by_cat)


@router.get("/kb/document", response_model=KbDocumentResponse)
def get_kb_document(kb_path: str = Query(..., description="Relative path under databases/knowledge_base/raw (e.g. 'procedures/pump-a.md').")) -> KbDocumentResponse:
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


@router.get("/suggestions/{suggestion_id}/original", response_model=OriginalDocumentResponse)
def get_suggestion_original(suggestion_id: str) -> OriginalDocumentResponse:
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


@router.get("/suggestions/{suggestion_id}/file")
def get_suggestion_file(suggestion_id: str) -> FileResponse:
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
    content_type = row["content_type"] or "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=original_filename,
        headers={"Content-Disposition": f'inline; filename="{original_filename}"'},
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
