from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


class DocumentAuthzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory(prefix="workflow-db-")
        cls._db_path = Path(cls._tmp_dir.name) / "workflow.sqlite3"
        os.environ["WORKFLOW_DB_PATH"] = str(cls._db_path)

        # Import after setting WORKFLOW_DB_PATH so startup initializes isolated DB.
        from app.main import app

        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_cm.__exit__(None, None, None)
        try:
            cls._tmp_dir.cleanup()
        except PermissionError:
            # SQLite files may remain briefly locked on Windows; ignore temp cleanup failure.
            pass

    def _login(self, *, email: str, password: str) -> dict:
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _create_document(self, title: str) -> dict:
        response = self.client.post(
            "/api/documents",
            json={
                "title": title,
                "fileName": f"{title.lower().replace(' ', '-')}.txt",
                "category": "sikkerhet",
                "uploadedBy": "Auth Test",
                "originalContent": "orig",
                "revisedContent": "rev",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _seed_non_privileged_user(self) -> None:
        email = "viewer@glencore.com"
        password = "viewer123"
        iterations = 150000
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        password_hash = f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (email,)).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO users (id, username, password_hash, display_name, role, is_active)
                    VALUES (?, ?, ?, ?, 'user', 1)
                    """,
                    (str(uuid.uuid4()), email, password_hash, "Viewer User"),
                )
            else:
                conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, role = 'user', is_active = 1, updated_at = datetime('now')
                    WHERE username = ?
                    """,
                    (password_hash, email),
                )

    def test_no_token_blocked(self) -> None:
        document = self._create_document("No Token Case")

        response = self.client.patch(f"/api/documents/{document['id']}/approve")

        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")

    def test_expert_can_approve_and_reject(self) -> None:
        login = self._login(email="expert@glencore.com", password="admin123")
        headers = {"Authorization": f"Bearer {login['accessToken']}"}

        pending_approve = self._create_document("Expert Approve Case")
        pending_reject = self._create_document("Expert Reject Case")

        approve_response = self.client.patch(
            f"/api/documents/{pending_approve['id']}/approve",
            headers=headers,
        )
        reject_response = self.client.patch(
            f"/api/documents/{pending_reject['id']}/reject",
            headers=headers,
        )

        self.assertEqual(approve_response.status_code, 200, approve_response.text)
        self.assertEqual(reject_response.status_code, 200, reject_response.text)
        self.assertEqual(approve_response.json()["status"], "approved")
        self.assertEqual(reject_response.json()["status"], "rejected")

    def test_non_privileged_user_gets_403(self) -> None:
        self._seed_non_privileged_user()
        viewer_login = self._login(email="viewer@glencore.com", password="viewer123")
        viewer_headers = {"Authorization": f"Bearer {viewer_login['accessToken']}"}
        document = self._create_document("Viewer Forbidden Case")

        response = self.client.patch(
            f"/api/documents/{document['id']}/approve",
            headers=viewer_headers,
        )

        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"]["code"], "FORBIDDEN")

    def test_logged_out_token_blocked(self) -> None:
        login = self._login(email="expert@glencore.com", password="admin123")
        headers = {"Authorization": f"Bearer {login['accessToken']}"}
        document = self._create_document("Logout Block Case")

        logout_response = self.client.post("/api/auth/logout", headers=headers)
        delete_response = self.client.delete(f"/api/documents/{document['id']}", headers=headers)

        self.assertEqual(logout_response.status_code, 204, logout_response.text)
        self.assertEqual(delete_response.status_code, 401, delete_response.text)
        self.assertEqual(delete_response.json()["error"]["code"], "UNAUTHORIZED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
