from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.workflow_db.db import get_connection

router = APIRouter(prefix="/api/auth", tags=["api-auth"])

ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))
REFRESH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "604800"))
PASSWORD_HASH_ITERATIONS = int(os.getenv("AUTH_PASSWORD_HASH_ITERATIONS", "150000"))

DEFAULT_USERNAME = os.getenv("AUTH_DEFAULT_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("AUTH_DEFAULT_PASSWORD", "admin123")
DEFAULT_DISPLAY_NAME = os.getenv("AUTH_DEFAULT_DISPLAY_NAME", "System Admin")
DEFAULT_EMAIL = os.getenv("AUTH_DEFAULT_EMAIL", DEFAULT_USERNAME)
if "@" not in DEFAULT_EMAIL:
    DEFAULT_EMAIL = "expert@glencore.com"
DEFAULT_ROLE = os.getenv("AUTH_DEFAULT_ROLE", "expert")

Role = Literal["admin", "reviewer", "user", "expert", "employee"]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthUserOut(BaseModel):
    id: str
    email: str
    username: str
    displayName: str
    role: Role


class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: Literal["bearer"] = "bearer"
    expiresIn: int
    user: AuthUserOut


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=16)


class RefreshResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: Literal["bearer"] = "bearer"
    expiresIn: int


class VerifyResponse(BaseModel):
    valid: bool
    user: AuthUserOut
    expiresAt: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    # SQLite values might not include timezone, treat as UTC for consistency.
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_password(password: str, salt_bytes: bytes) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt_bytes.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iter_raw, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iter_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _random_token(prefix: str) -> str:
    raw = secrets.token_bytes(48)
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{prefix}_{token}"


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Missing Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid Authorization header")

    return parts[1].strip()


def _validate_email_or_raise(value: str) -> str:
    normalized = value.strip().lower()
    if not EMAIL_PATTERN.match(normalized):
        raise _api_error(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", "Invalid email format")
    return normalized


def _row_to_user(row) -> AuthUserOut:
    role = str(row["role"] or "").strip().lower()
    if role in {"reviewer", "user", "viewer"}:
        role = "employee"
    return AuthUserOut(
        id=row["id"],
        email=row["username"],
        username=row["username"],
        displayName=row["display_name"],
        role=role,
    )


def _role_supported(conn, role: str) -> bool:
    table_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if table_row is None:
        return role in {"admin", "reviewer", "user", "expert", "employee"}

    create_sql = (table_row["sql"] or "").lower()
    return f"'{role}'" in create_sql


def _ensure_default_user(conn) -> None:
    default_email = _validate_email_or_raise(DEFAULT_EMAIL)

    desired_role = DEFAULT_ROLE if DEFAULT_ROLE in {"admin", "reviewer", "user", "expert", "employee"} else "expert"
    if desired_role == "employee":
        # Keep DB compatibility where role CHECK might still use legacy values.
        desired_role = "reviewer"
    if not _role_supported(conn, desired_role):
        desired_role = "admin"

    # One-time compatibility migration: convert legacy "admin" login to email if possible.
    legacy = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    has_default = conn.execute("SELECT id, role FROM users WHERE username = ?", (default_email,)).fetchone()
    if legacy is not None and has_default is None:
        conn.execute(
            "UPDATE users SET username = ?, role = ?, updated_at = datetime('now') WHERE id = ?",
            (default_email, desired_role, legacy["id"]),
        )

    if has_default is not None and has_default["role"] != desired_role:
        conn.execute(
            "UPDATE users SET role = ?, updated_at = datetime('now') WHERE id = ?",
            (desired_role, has_default["id"]),
        )

    existing = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
    if existing is not None:
        return

    role = desired_role
    salt = secrets.token_bytes(16)
    conn.execute(
        """
        INSERT INTO users (id, username, password_hash, display_name, role, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            str(uuid.uuid4()),
            default_email,
            _hash_password(DEFAULT_PASSWORD, salt),
            DEFAULT_DISPLAY_NAME,
            role,
        ),
    )


def _find_active_session_by_access_hash(conn, access_hash: str):
    return conn.execute(
        """
        SELECT s.id, s.user_id, s.access_expires_at, s.refresh_expires_at,
               u.id AS uid, u.username, u.display_name, u.role, u.is_active
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.access_token_hash = ?
          AND s.revoked_at IS NULL
        """,
        (access_hash,),
    ).fetchone()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    login_identifier = payload.email or payload.username
    if not login_identifier or not login_identifier.strip():
        raise _api_error(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", "email or username is required")

    username = _validate_email_or_raise(login_identifier)

    with get_connection() as conn:
        _ensure_default_user(conn)

        user = conn.execute(
            """
            SELECT id, username, password_hash, display_name, role, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if user is None or not _verify_password(payload.password, user["password_hash"]):
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid username or password")

        if int(user["is_active"] or 0) != 1:
            raise _api_error(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "User is inactive")

        access_token = _random_token("atk")
        refresh_token = _random_token("rtk")

        now = _utc_now()
        access_expires = now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        refresh_expires = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)

        conn.execute(
            """
            INSERT INTO auth_sessions (
                id, user_id, access_token_hash, refresh_token_hash,
                access_expires_at, refresh_expires_at, revoked_at, last_refreshed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                str(uuid.uuid4()),
                user["id"],
                _hash_token(access_token),
                _hash_token(refresh_token),
                _iso(access_expires),
                _iso(refresh_expires),
            ),
        )

    return LoginResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=ACCESS_TOKEN_TTL_SECONDS,
        user=_row_to_user(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> None:
    token = _extract_bearer_token(authorization)
    token_hash = _hash_token(token)

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE access_token_hash = ?
              AND revoked_at IS NULL
            """,
            (_iso(_utc_now()), token_hash),
        )

        if result.rowcount == 0:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid or expired token")


@router.post("/refresh", response_model=RefreshResponse)
def refresh(payload: RefreshRequest) -> RefreshResponse:
    refresh_hash = _hash_token(payload.refreshToken)
    now = _utc_now()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, refresh_expires_at, revoked_at
            FROM auth_sessions
            WHERE refresh_token_hash = ?
            """,
            (refresh_hash,),
        ).fetchone()

        if row is None or row["revoked_at"] is not None:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid refresh token")

        if _parse_iso(row["refresh_expires_at"]) <= now:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE id = ?",
                (_iso(now), row["id"]),
            )
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Refresh token expired")

        new_access = _random_token("atk")
        new_refresh = _random_token("rtk")
        access_expires = now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)
        refresh_expires = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)

        conn.execute(
            """
            UPDATE auth_sessions
            SET access_token_hash = ?,
                refresh_token_hash = ?,
                access_expires_at = ?,
                refresh_expires_at = ?,
                last_refreshed_at = ?
            WHERE id = ?
            """,
            (
                _hash_token(new_access),
                _hash_token(new_refresh),
                _iso(access_expires),
                _iso(refresh_expires),
                _iso(now),
                row["id"],
            ),
        )

    return RefreshResponse(
        accessToken=new_access,
        refreshToken=new_refresh,
        expiresIn=ACCESS_TOKEN_TTL_SECONDS,
    )


@router.get("/verify", response_model=VerifyResponse)
def verify(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> VerifyResponse:
    token = _extract_bearer_token(authorization)
    token_hash = _hash_token(token)
    now = _utc_now()

    with get_connection() as conn:
        row = _find_active_session_by_access_hash(conn, token_hash)

        if row is None:
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Invalid token")

        if int(row["is_active"] or 0) != 1:
            raise _api_error(status.HTTP_403_FORBIDDEN, "FORBIDDEN", "User is inactive")

        access_expires = _parse_iso(row["access_expires_at"])
        if access_expires <= now:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE id = ?",
                (_iso(now), row["id"]),
            )
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "Token expired")

    user = _row_to_user(
        {
            "id": row["uid"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role"],
        }
    )

    return VerifyResponse(valid=True, user=user, expiresAt=_iso(access_expires))
