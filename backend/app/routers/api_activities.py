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
