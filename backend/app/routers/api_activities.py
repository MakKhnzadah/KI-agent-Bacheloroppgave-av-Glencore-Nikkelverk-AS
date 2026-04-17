from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.workflow_db.db import get_connection

router = APIRouter(prefix="/api/activities", tags=["api-activities"])

ActivityType = Literal[
    "document_approved",
    "document_uploaded",
    "ai_suggestion",
    "document_rejected",
    "system_update",
]


class ActivityOut(BaseModel):
    id: str
    type: ActivityType
    title: str
    description: str
    user: str
    time: str
    documentId: Optional[str] = None


class ActivityCreateRequest(BaseModel):
    type: ActivityType
    title: str
    description: str
    user: str
    documentId: Optional[str] = None
    time: Optional[str] = None


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


def _insert_activity_row(conn, *, activity_type: str, title: str, description: str, user: str, time_value: str) -> None:
    conn.execute(
        """
        INSERT INTO activities (id, type, title, description, user, time, document_id)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (str(uuid.uuid4()), activity_type, title, description, user, time_value),
    )


def _backfill_activities_if_empty(conn) -> None:
    existing_count = conn.execute("SELECT COUNT(*) AS n FROM activities").fetchone()["n"]
    if int(existing_count or 0) > 0:
        return

    uploads = conn.execute(
        """
        SELECT original_filename
        FROM uploads
        ORDER BY created_at DESC
        LIMIT 20
        """
    ).fetchall()
    for row in uploads:
        desc = (row["original_filename"] or "Dokument").strip()
        _insert_activity_row(
            conn,
            activity_type="document_uploaded",
            title="Dokument lastet opp",
            description=desc,
            user="System",
            time_value="tidligere",
        )

    reviews = conn.execute(
        """
        SELECT r.decision, COALESCE(r.reviewer, 'System') AS reviewer, u.original_filename
        FROM reviews r
        JOIN suggestions s ON s.suggestion_id = r.suggestion_id
        LEFT JOIN uploads u ON u.upload_id = s.upload_id
        ORDER BY r.created_at DESC
        LIMIT 20
        """
    ).fetchall()

    for row in reviews:
        decision = (row["decision"] or "").strip().lower()
        desc = (row["original_filename"] or "Dokument").strip()
        reviewer = (row["reviewer"] or "System").strip()
        if decision == "approved":
            _insert_activity_row(
                conn,
                activity_type="document_approved",
                title="Nytt dokument godkjent",
                description=desc,
                user=reviewer,
                time_value="tidligere",
            )
        elif decision == "rejected":
            _insert_activity_row(
                conn,
                activity_type="document_rejected",
                title="Dokument avvist",
                description=desc,
                user=reviewer,
                time_value="tidligere",
            )


@router.get("", response_model=list[ActivityOut])
def list_activities(
    limit: int = Query(default=10, ge=1, le=100),
    user: Optional[str] = Query(default=None),
) -> list[ActivityOut]:
    query = """
        SELECT id, type, title, description, user, time, document_id
        FROM activities
        WHERE 1 = 1
    """
    params: list[object] = []

    if user:
        query += " AND user = ?"
        params.append(user)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        _backfill_activities_if_empty(conn)
        rows = conn.execute(query, params).fetchall()

    return [_row_to_activity(row) for row in rows]


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(payload: ActivityCreateRequest) -> ActivityOut:
    activity_id = str(uuid.uuid4())
    time_value = payload.time or "nå"

    with get_connection() as conn:
        if payload.documentId:
            exists = conn.execute("SELECT id FROM documents WHERE id = ?", (payload.documentId,)).fetchone()
            if exists is None:
                raise _api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Document not found")

        conn.execute(
            """
            INSERT INTO activities (id, type, title, description, user, time, document_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                activity_id,
                payload.type,
                payload.title,
                payload.description,
                payload.user,
                time_value,
                payload.documentId,
            ),
        )

        row = conn.execute(
            """
            SELECT id, type, title, description, user, time, document_id
            FROM activities
            WHERE id = ?
            """,
            (activity_id,),
        ).fetchone()

    return _row_to_activity(row)
