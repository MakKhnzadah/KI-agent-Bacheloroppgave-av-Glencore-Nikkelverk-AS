from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.workflow_db.db import get_connection

router = APIRouter(prefix="/api/documents", tags=["api-documents"])

DocumentStatus = Literal["pending", "approved", "rejected"]
DocumentCategory = Literal["Sikkerhet", "Vedlikehold", "Miljø", "Kvalitet", "Prosedyre", "Annet"]

_CATEGORY_MAP = {
    "sikkerhet": "Sikkerhet",
    "vedlikehold": "Vedlikehold",
    "miljo": "Miljø",
    "miljø": "Miljø",
    "kvalitet": "Kvalitet",
    "prosedyre": "Prosedyre",
    "annet": "Annet",
}

_MONTHS_NB = [
    "jan",
    "feb",
    "mar",
    "apr",
    "mai",
    "jun",
    "jul",
    "aug",
    "sep",
    "okt",
    "nov",
    "des",
]


class DocumentOut(BaseModel):
    id: str
    title: str
    fileName: str
    category: DocumentCategory
    status: DocumentStatus
    uploadedBy: str
    uploadedAt: str
    originalContent: str
    revisedContent: str
    approvedContent: Optional[str] = None


class DocumentCreateRequest(BaseModel):
    title: str
    fileName: str
    category: str
    uploadedBy: str
    originalContent: str = ""
    revisedContent: str = ""


class DocumentStatsOut(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int


class ActivityOut(BaseModel):
    id: str
    type: Literal[
        "document_approved",
        "document_uploaded",
        "ai_suggestion",
        "document_rejected",
        "system_update",
    ]
    title: str
    description: str
    user: str
    time: str
    documentId: Optional[str] = None


class DocumentDecisionRequest(BaseModel):
    reviewer: Optional[str] = None
    comment: Optional[str] = None


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


def _format_uploaded_at(now: datetime) -> str:
    # Matches frontend mock style, e.g. "10. feb 2026 - 14:30"
    return f"{now.day}. {_MONTHS_NB[now.month - 1]} {now.year} - {now:%H:%M}"


def _normalize_category(value: str) -> DocumentCategory:
    cleaned = (value or "").strip()
    mapped = _CATEGORY_MAP.get(cleaned.lower())
    if mapped is not None:
        return mapped  # type: ignore[return-value]

    # Accept exact contract values too.
    if cleaned in {"Sikkerhet", "Vedlikehold", "Miljø", "Kvalitet", "Prosedyre", "Annet"}:
        return cleaned  # type: ignore[return-value]

    raise _api_error(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", f"Invalid category: {value}")


def _row_to_document(row) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        title=row["title"],
        fileName=row["file_name"],
        category=row["category"],
        status=row["status"],
        uploadedBy=row["uploaded_by"],
        uploadedAt=row["uploaded_at"],
        originalContent=row["original_content"],
        revisedContent=row["revised_content"],
        approvedContent=row["approved_content"],
    )


def _insert_activity(
    conn,
    *,
    activity_type: str,
    title: str,
    description: str,
    user: str,
    time_label: str,
    document_id: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO activities (id, type, title, description, user, time, document_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), activity_type, title, description, user, time_label, document_id),
    )


def _insert_audit(
    conn,
    *,
    document_id: str,
    action: str,
    from_status: Optional[str],
    to_status: Optional[str],
    performed_by: str,
    comment: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO document_audits (id, document_id, action, from_status, to_status, performed_by, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), document_id, action, from_status, to_status, performed_by, comment),
    )


def _row_to_activity(row) -> ActivityOut:
    return ActivityOut(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        description=row["description"],
        user=row["user"],
        time=row["time"],
        documentId=row["document_id"],
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


def _require_expert_user(authorization: Optional[str]) -> str:
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

    if row["role"] != "expert":
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Insufficient role",
            details={"requiredRole": "expert", "currentRole": row["role"]},
        )

    return row["username"]


@router.get("", response_model=list[DocumentOut])
def list_documents(
    status: Optional[DocumentStatus] = Query(default=None),
    category: Optional[str] = Query(default=None),
) -> list[DocumentOut]:
    query = """
        SELECT id, title, file_name, category, status, uploaded_by, uploaded_at,
               original_content, revised_content, approved_content
        FROM documents
        WHERE 1 = 1
    """
    params: list[str] = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if category:
        normalized = _normalize_category(category)
        query += " AND category = ?"
        params.append(normalized)

    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_document(row) for row in rows]


@router.get("/stats", response_model=DocumentStatsOut)
def get_document_stats() -> DocumentStatsOut:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
            FROM documents
            """
        ).fetchone()

    return DocumentStatsOut(
        total=int(row["total"] or 0),
        pending=int(row["pending"] or 0),
        approved=int(row["approved"] or 0),
        rejected=int(row["rejected"] or 0),
    )


@router.get("/search", response_model=list[DocumentOut])
def search_documents(q: str = Query(..., min_length=1)) -> list[DocumentOut]:
    like = f"%{q.strip()}%"

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, file_name, category, status, uploaded_by, uploaded_at,
                   original_content, revised_content, approved_content
            FROM documents
            WHERE title LIKE ?
               OR file_name LIKE ?
               OR category LIKE ?
               OR original_content LIKE ?
               OR revised_content LIKE ?
            ORDER BY created_at DESC
            """,
            (like, like, like, like, like),
        ).fetchall()

    return [_row_to_document(row) for row in rows]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str) -> DocumentOut:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, file_name, category, status, uploaded_by, uploaded_at,
                   original_content, revised_content, approved_content
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

    if row is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

    return _row_to_document(row)


@router.get("/{document_id}/activities", response_model=list[ActivityOut])
def get_document_activities(document_id: str) -> list[ActivityOut]:
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone()
        if existing is None:
            raise _api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

        rows = conn.execute(
            """
            SELECT id, type, title, description, user, time, document_id
            FROM activities
            WHERE document_id = ?
            ORDER BY created_at DESC
            """,
            (document_id,),
        ).fetchall()

    return [_row_to_activity(row) for row in rows]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreateRequest) -> DocumentOut:
    now = datetime.now()
    doc_id = str(uuid.uuid4())
    category = _normalize_category(payload.category)

    original = (payload.originalContent or "").strip()
    revised = (payload.revisedContent or "").strip()

    if not original:
        original = (
            f"{payload.title}\n\n"
            "Dette er det originale dokumentet som ble lastet opp.\n"
            "Innholdet vil bli analysert og revidert av AI-systemet."
        )

    if not revised:
        revised = (
            f"{payload.title} - AI Revidert\n\n"
            "Dette er den reviderte versjonen av dokumentet etter AI-analyse.\n"
            "Dokumentet venter pa godkjenning."
        )

    uploaded_at = _format_uploaded_at(now)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                id, title, file_name, category, status, uploaded_by, uploaded_at,
                original_content, revised_content, approved_content, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                doc_id,
                payload.title,
                payload.fileName,
                category,
                "pending",
                payload.uploadedBy,
                uploaded_at,
                original,
                revised,
                None,
            ),
        )

        _insert_audit(
            conn,
            document_id=doc_id,
            action="created",
            from_status=None,
            to_status="pending",
            performed_by=payload.uploadedBy,
            comment="Document created via API",
        )
        _insert_activity(
            conn,
            activity_type="document_uploaded",
            title="Dokument lastet opp",
            description=payload.title,
            user=payload.uploadedBy,
            time_label="nå",
            document_id=doc_id,
        )

        row = conn.execute(
            """
            SELECT id, title, file_name, category, status, uploaded_by, uploaded_at,
                   original_content, revised_content, approved_content
            FROM documents
            WHERE id = ?
            """,
            (doc_id,),
        ).fetchone()

    return _row_to_document(row)


@router.patch("/{document_id}/approve", response_model=DocumentOut)
def approve_document(
    document_id: str,
    payload: Optional[DocumentDecisionRequest] = Body(default=None),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> DocumentOut:
    reviewer = _require_expert_user(authorization)
    comment = payload.comment if payload else None

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, title, status FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()

        if existing is None:
            raise _api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

        if existing["status"] != "pending":
            raise _api_error(
                status.HTTP_409_CONFLICT,
                "CONFLICT",
                "Only pending documents can be approved",
                details={"currentStatus": existing["status"]},
            )

        conn.execute(
            """
            UPDATE documents
            SET status = 'approved',
                approved_content = revised_content,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (document_id,),
        )

        _insert_audit(
            conn,
            document_id=document_id,
            action="approved",
            from_status="pending",
            to_status="approved",
            performed_by=reviewer,
            comment=comment,
        )
        _insert_activity(
            conn,
            activity_type="document_approved",
            title="Nytt dokument godkjent",
            description=existing["title"],
            user=reviewer,
            time_label="nå",
            document_id=document_id,
        )

        row = conn.execute(
            """
            SELECT id, title, file_name, category, status, uploaded_by, uploaded_at,
                   original_content, revised_content, approved_content
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

    return _row_to_document(row)


@router.patch("/{document_id}/reject", response_model=DocumentOut)
def reject_document(
    document_id: str,
    payload: Optional[DocumentDecisionRequest] = Body(default=None),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> DocumentOut:
    reviewer = _require_expert_user(authorization)
    comment = payload.comment if payload else None

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, title, status FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()

        if existing is None:
            raise _api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

        if existing["status"] != "pending":
            raise _api_error(
                status.HTTP_409_CONFLICT,
                "CONFLICT",
                "Only pending documents can be rejected",
                details={"currentStatus": existing["status"]},
            )

        conn.execute(
            """
            UPDATE documents
            SET status = 'rejected',
                approved_content = NULL,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (document_id,),
        )

        _insert_audit(
            conn,
            document_id=document_id,
            action="rejected",
            from_status="pending",
            to_status="rejected",
            performed_by=reviewer,
            comment=comment,
        )
        _insert_activity(
            conn,
            activity_type="document_rejected",
            title="Dokument avvist",
            description=existing["title"],
            user=reviewer,
            time_label="nå",
            document_id=document_id,
        )

        row = conn.execute(
            """
            SELECT id, title, file_name, category, status, uploaded_by, uploaded_at,
                   original_content, revised_content, approved_content
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

    return _row_to_document(row)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Response:
    _require_expert_user(authorization)

    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,)).rowcount

    if deleted == 0:
        raise _api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
