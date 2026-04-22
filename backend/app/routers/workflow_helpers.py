from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from fastapi import HTTPException, status
from yaml import YAMLError

from app.vector_store.config import _repo_root_from_here, load_vector_store_config
from app.workflow_db.db import get_connection

logger = logging.getLogger(__name__)

_reindex_lock = threading.Lock()
_reindex_status_lock = threading.Lock()
_reindex_status: dict[str, object | None] = {
    "state": "idle",
    "current_run_id": None,
    "last_completed_run_id": None,
    "last_reason": None,
    "last_started_at": None,
    "last_finished_at": None,
    "last_error": None,
    "last_indexed_files": None,
    "last_indexed_chunks": None,
}


def _looks_like_non_norwegian(text: str) -> bool:
    body = (text or "").strip()
    if not body:
        return False

    head = body[:4500].lower()
    head = re.sub(r"(?m)^#{1,6}\s+", "", head)
    head = re.sub(r"[`*_>\[\]\(\)\{\}|]", " ", head)
    words = re.findall(r"[a-zæøå]+", head, flags=re.IGNORECASE)
    if len(words) < 80:
        return False

    norwegian = {"og", "ikke", "som", "for", "med", "til", "av", "på", "i", "skal", "kan", "må", "krav", "tiltak"}
    english = {"the", "and", "to", "of", "in", "for", "with", "this", "that", "should", "must", "summary", "recommendations", "proposal"}

    n_count = sum(1 for w in words if w in norwegian)
    e_count = sum(1 for w in words if w in english)
    return e_count >= 14 and e_count > (n_count * 1.4) and n_count < 12


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _set_reindex_status(**updates: object | None) -> None:
    with _reindex_status_lock:
        _reindex_status.update(updates)


def _mark_reindex_scheduled(reason: str) -> str:
    run_id = str(uuid.uuid4())
    _set_reindex_status(
        state="scheduled",
        current_run_id=run_id,
        last_reason=reason,
        last_error=None,
        last_started_at=None,
        last_finished_at=None,
        last_indexed_files=None,
        last_indexed_chunks=None,
    )
    return run_id


def get_reindex_status_snapshot() -> dict[str, object | None]:
    with _reindex_status_lock:
        return dict(_reindex_status)


def _api_error(status_code: int, code: str, message: str, details: Optional[dict] = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Missing Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid Authorization header")

    return parts[1].strip()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_external_role(role: str) -> str:
    """Normalize legacy role names for externally visible RBAC decisions."""

    raw = (role or "").strip().lower()
    if raw in {"reviewer", "user", "viewer"}:
        return "employee"
    return raw


def _require_authenticated_user(
    authorization: Optional[str],
    *,
    allowed_roles: Optional[set[str]] = None,
) -> tuple[str, str]:
    token = _extract_bearer_token(authorization)
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.id, s.access_expires_at, u.username, u.role, u.is_active
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.access_token_hash = ?
              AND s.revoked_at IS NULL
            """,
            (token_hash,),
        ).fetchone()

    if row is None:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid token")

    if int(row["is_active"] or 0) != 1:
        raise _api_error(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "User is inactive")

    if _parse_iso(row["access_expires_at"]) <= now:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Token expired")

    current_role = _normalize_external_role(str(row["role"] or ""))
    if allowed_roles is not None and current_role not in allowed_roles:
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Insufficient role",
            details={"requiredRoles": sorted(allowed_roles), "currentRole": current_role},
        )

    return str(row["username"]), current_role


def _require_expert_user(authorization: Optional[str]) -> str:
    username, _ = _require_authenticated_user(authorization, allowed_roles={"expert", "admin"})
    return username


def _reindex_kb_to_chroma(run_id: Optional[str] = None) -> None:
    if not _reindex_lock.acquire(blocking=False):
        logger.info("KB re-index already in progress; skipping duplicate request")
        _set_reindex_status(
            state="in_progress",
            last_error=None,
        )
        return

    active_run_id = run_id or str(uuid.uuid4())

    _set_reindex_status(
        state="in_progress",
        current_run_id=active_run_id,
        last_started_at=_utc_now_iso(),
        last_finished_at=None,
        last_error=None,
        last_indexed_files=None,
        last_indexed_chunks=None,
    )

    try:
        try:
            from app.vector_store.chroma_store import ChromaVectorStore
            from app.vector_store.kb_indexer import index_kb
            from app.vector_store.ollama_embeddings import OllamaEmbeddingClient
        except Exception as exc:
            logger.info("Vector search disabled (chromadb not installed); skipping KB re-index")
            _set_reindex_status(
                state="skipped",
                last_completed_run_id=active_run_id,
                last_finished_at=_utc_now_iso(),
                last_error=f"Vector search dependencies are unavailable: {exc}",
            )
            return

        cfg = load_vector_store_config()
        store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
        embedder = OllamaEmbeddingClient(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_embed_model,
            timeout_s=cfg.ollama_embed_timeout_s,
        )

        try:
            stats = index_kb(store=store, embedder=embedder)
            logger.info(
                "KB re-index completed: files=%s chunks=%s persist_dir=%s",
                stats.get("files"),
                stats.get("chunks"),
                str(cfg.persist_dir),
            )
            _set_reindex_status(
                state="completed",
                last_completed_run_id=active_run_id,
                last_finished_at=_utc_now_iso(),
                last_error=None,
                last_indexed_files=stats.get("files"),
                last_indexed_chunks=stats.get("chunks"),
            )
        except Exception as exc:
            logger.exception("KB re-index failed")
            _set_reindex_status(
                state="failed",
                last_completed_run_id=active_run_id,
                last_finished_at=_utc_now_iso(),
                last_error=f"KB re-index failed: {exc}",
            )
    finally:
        _reindex_lock.release()


def _external_status(db_status: str) -> str:
    if db_status == "draft":
        return "pending_approval"
    return db_status


def _split_front_matter(doc: str) -> tuple[dict, str]:
    text = doc.lstrip("\ufeff")
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

    def parse(raw: str) -> dict:
        parsed = yaml.safe_load(raw) or {}
        return parsed if isinstance(parsed, dict) else {}

    try:
        return parse(front_raw), body
    except YAMLError:
        repaired_lines = []
        for line in front_raw.splitlines():
            if line.startswith("title:"):
                value = line[len("title:") :].strip()
                if value and not (value.startswith('"') or value.startswith("'")) and ":" in value:
                    safe = value.replace("\\", "\\\\").replace('"', '\\"')
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


def _kb_raw_root() -> Path:
    repo_root = _repo_root_from_here()
    return Path(repo_root) / "databases" / "knowledge_base" / "raw"


def _resolve_kb_path(kb_path: str) -> Path:
    root = _kb_raw_root().resolve()
    rel = Path(kb_path)
    rel = Path(*rel.parts)
    if rel.is_absolute():
        raise ValueError("kb_path must be relative")

    full = (root / rel).resolve()
    if root not in full.parents and full != root:
        raise ValueError("kb_path escapes KB root")
    if full.suffix.lower() != ".md":
        raise ValueError("kb_path must end with .md")
    return full


def _next_available_kb_path(base_name: str, suggestion_id: str) -> Path:
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
        h = hashlib.blake2b(sh.encode("utf-8"), digest_size=8).digest()
        out.add(int.from_bytes(h, "big"))
        if len(out) >= max_shingles:
            break
    return out


def _similarity_metrics(new_text: str, existing_text: str) -> tuple[float, float, float]:
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


def _read_text_best_effort(path: Path, *, max_chars: int = 300_000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars]
    return text
