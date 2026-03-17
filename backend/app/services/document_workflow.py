from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException

from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT
from app.agents.suggestion_agent import SUGGESTION_AGENT_PROMPT
from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.document_processing.document_parsing import parse_document
from app.vector_store.config import _repo_root_from_here
from app.workflow_db.db import get_connection


# Keep these as module-level singletons for the MVP.
# This avoids re-creating the provider/service on every request.
_llm_provider = OllamaProvider()
_agent = AgentService(_llm_provider)


_WORD_RE = re.compile(r"[A-Za-z0-9_]{3,}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _simhash64(text: str) -> int:
    """Compute a simple 64-bit SimHash for near-duplicate detection."""

    words = _WORD_RE.findall((text or "").lower())
    if not words:
        return 0

    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    v = [0] * 64
    for token, weight in freq.items():
        h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        x = int.from_bytes(h, byteorder="big", signed=False)
        for i in range(64):
            bit = (x >> i) & 1
            v[i] += weight if bit else -weight

    out = 0
    for i, val in enumerate(v):
        if val >= 0:
            out |= 1 << i
    return out


def _simhash_similarity(a: int, b: int) -> float:
    # 0..1 where 1 == identical
    return 1.0 - ((a ^ b).bit_count() / 64.0)


def process_upload(*, filename: str, content: bytes, content_type: str | None) -> dict:
    """Process an uploaded document.

    - De-duplicates exact duplicate files by sha256(content).
    - Optionally checks near-duplicates by text similarity (SimHash).
    - Parses the document and runs 2-step LLM flow (draft + suggestions section).
    - Persists upload, normalized text, and draft suggestion into workflow DB.

    Returns the same response shape as the API endpoint.
    """

    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    content_sha256 = _sha256_bytes(content)

    ext = os.path.splitext(filename.lower())[1]
    if ext not in {".pdf", ".txt", ".md", ".docx", ".eml"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Exact duplicate check (bytes hash).
    with get_connection() as conn:
        existing_upload = conn.execute(
            """
            SELECT upload_id
            FROM uploads
            WHERE sha256 = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (content_sha256,),
        ).fetchone()

        if existing_upload is not None:
            existing_suggestion = conn.execute(
                """
                SELECT suggestion_id, suggestion_json, status
                FROM suggestions
                WHERE upload_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (existing_upload["upload_id"],),
            ).fetchone()

            if existing_suggestion is None:
                raise HTTPException(
                    status_code=409,
                    detail="Duplicate upload found, but no suggestion exists for it",
                )

            return {
                "upload_id": existing_upload["upload_id"],
                "suggestion_id": existing_suggestion["suggestion_id"],
                "structured_draft": existing_suggestion["suggestion_json"],
                "suggestion_addon": "",
                "status": "pending_approval" if existing_suggestion["status"] == "draft" else existing_suggestion["status"],
                "deduped": True,
            }

    try:
        processed_text = parse_document(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {exc}")
    if not processed_text or not processed_text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the document")

    # Near-duplicate detection (optional): compare extracted text to recent documents.
    similarity_threshold = float(os.getenv("UPLOAD_SIMILARITY_THRESHOLD", "0.92"))
    compare_limit = int(os.getenv("UPLOAD_SIMILARITY_COMPARE_LIMIT", "200"))

    text_sample = processed_text[:50000]
    new_fp = _simhash64(text_sample)

    if new_fp != 0 and compare_limit > 0 and similarity_threshold > 0:
        best = None  # (similarity, upload_id)

        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT n.upload_id, substr(n.text, 1, 50000) AS text_sample
                FROM normalized_documents n
                ORDER BY n.created_at DESC
                LIMIT ?
                """,
                (compare_limit,),
            ).fetchall()

            for row in rows:
                existing_fp = _simhash64(row["text_sample"] or "")
                if existing_fp == 0:
                    continue
                sim = _simhash_similarity(new_fp, existing_fp)
                if best is None or sim > best[0]:
                    best = (sim, row["upload_id"])

            if best is not None and best[0] >= similarity_threshold:
                existing_suggestion = conn.execute(
                    """
                    SELECT suggestion_id, suggestion_json, status
                    FROM suggestions
                    WHERE upload_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (best[1],),
                ).fetchone()

                if existing_suggestion is None:
                    raise HTTPException(
                        status_code=409,
                        detail="Similar document found, but no suggestion exists for it",
                    )

                return {
                    "upload_id": best[1],
                    "suggestion_id": existing_suggestion["suggestion_id"],
                    "structured_draft": existing_suggestion["suggestion_json"],
                    "suggestion_addon": "",
                    "status": "pending_approval" if existing_suggestion["status"] == "draft" else existing_suggestion["status"],
                    "deduped": True,
                    "dedupe_method": "similarity",
                    "similarity": best[0],
                }

    # 1) Structured KB draft (YAML + Markdown).
    structured_draft = _agent.process_document(STRUCTURING_AGENT_PROMPT, processed_text)

    # 2) Add-on suggestions section derived from the structured draft.
    suggestion_addon = _agent.process_document(SUGGESTION_AGENT_PROMPT, structured_draft)

    upload_id = str(uuid.uuid4())
    normalized_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    normalized_sha256 = _sha256_text(processed_text)

    # Persist artifacts to disk for traceability in the MVP.
    repo_root = _repo_root_from_here()
    data_root = Path(repo_root) / "databases" / "data"
    uploads_dir = Path(os.getenv("UPLOAD_STORE_DIR", str(data_root / "uploads")))
    normalized_dir = Path(os.getenv("NORMALIZED_STORE_DIR", str(data_root / "normalized")))
    suggestions_dir = Path(os.getenv("SUGGESTIONS_STORE_DIR", str(data_root / "suggestions")))

    uploads_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    suggestions_dir.mkdir(parents=True, exist_ok=True)

    def safe_name(name: str) -> str:
        out = []
        for ch in name:
            if ch.isalnum() or ch in {"_", ".", "-"}:
                out.append(ch)
            else:
                out.append("_")
        cleaned = "".join(out).strip("._")
        return cleaned or "upload"

    stored_upload_path = uploads_dir / f"{upload_id}_{safe_name(filename)}"
    stored_normalized_path = normalized_dir / f"{upload_id}.txt"
    stored_suggestion_path = suggestions_dir / f"{suggestion_id}.md"
    stored_addon_path = suggestions_dir / f"{suggestion_id}_addon.md"

    stored_upload_path.write_bytes(content)
    stored_normalized_path.write_text(processed_text, encoding="utf-8")
    stored_suggestion_path.write_text(structured_draft.rstrip() + "\n", encoding="utf-8")
    stored_addon_path.write_text(suggestion_addon.rstrip() + "\n", encoding="utf-8")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO uploads (upload_id, original_filename, content_type, size_bytes, sha256, stored_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                filename,
                content_type,
                len(content),
                content_sha256,
                str(stored_upload_path.as_posix()),
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
            (suggestion_id, upload_id, structured_draft, _llm_provider.model, "draft"),
        )

    return {
        "upload_id": upload_id,
        "suggestion_id": suggestion_id,
        "structured_draft": structured_draft,
        "suggestion_addon": suggestion_addon,
        "status": "pending_approval",
        "deduped": False,
    }
