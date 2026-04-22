from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class WorkflowApplyConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory(prefix="workflow-db-")
        cls._db_path = Path(cls._tmp_dir.name) / "workflow.sqlite3"
        os.environ["WORKFLOW_DB_PATH"] = str(cls._db_path)

        # Import after setting WORKFLOW_DB_PATH so startup initializes isolated DB.
        from app.main import app

        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

        cls._repo_root = Path(__file__).resolve().parents[2]
        cls._kb_root = cls._repo_root / "databases" / "knowledge_base" / "raw"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_cm.__exit__(None, None, None)
        try:
            cls._tmp_dir.cleanup()
        except PermissionError:
            pass

    def setUp(self) -> None:
        self._created_kb_files: list[Path] = []

    def tearDown(self) -> None:
        for path in self._created_kb_files:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def _login_expert_headers(self) -> dict[str, str]:
        response = self.client.post(
            "/api/auth/login",
            json={"email": "expert@glencore.com", "password": "admin123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["accessToken"]
        return {"Authorization": f"Bearer {token}"}

    def _upload_and_approve(self, *, headers: dict[str, str], marker: str) -> str:
        upload = self.client.post(
            "/documents/upload",
            files={"file": ("step4.txt", f"Step4 marker: {marker}".encode("utf-8"), "text/plain")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        suggestion_id = upload.json()["suggestion_id"]

        review = self.client.post(
            f"/workflow/suggestions/{suggestion_id}/review",
            headers=headers,
            json={"decision": "approved"},
        )
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(review.json()["status"], "approved")

        return suggestion_id

    def test_apply_persists_status_path_change_and_file(self) -> None:
        headers = self._login_expert_headers()
        marker = f"consistency-{uuid.uuid4().hex}"
        suggestion_id = self._upload_and_approve(headers=headers, marker=marker)

        rel_kb_path = f"test-artifacts/{marker}.md"
        with patch("app.routers.workflow._reindex_kb_to_chroma", return_value=None):
            apply_response = self.client.post(
                f"/workflow/suggestions/{suggestion_id}/apply",
                headers=headers,
                json={"kb_path": rel_kb_path, "notes": "step4 consistency"},
            )

        self.assertEqual(apply_response.status_code, 200, apply_response.text)
        body = apply_response.json()
        self.assertEqual(body["status"], "applied")
        self.assertEqual(body["reindex"], "scheduled")

        kb_file = Path(body["kb_path"])
        self._created_kb_files.append(kb_file)
        self.assertTrue(kb_file.exists())
        persisted = kb_file.read_text(encoding="utf-8", errors="replace")
        stable_token = marker.split("-", 1)[1] if "-" in marker else marker
        self.assertIn(stable_token, persisted)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            suggestion = conn.execute(
                "SELECT status, target_kb_path FROM suggestions WHERE suggestion_id = ?",
                (suggestion_id,),
            ).fetchone()
            self.assertIsNotNone(suggestion)
            self.assertEqual(suggestion["status"], "applied")
            self.assertEqual(suggestion["target_kb_path"], str(kb_file.as_posix()))

            applied_change = conn.execute(
                "SELECT suggestion_id, kb_path FROM applied_changes WHERE suggestion_id = ?",
                (suggestion_id,),
            ).fetchone()
            self.assertIsNotNone(applied_change)
            self.assertEqual(applied_change["suggestion_id"], suggestion_id)
            self.assertEqual(applied_change["kb_path"], str(kb_file.as_posix()))

    def test_apply_rejects_invalid_kb_path(self) -> None:
        headers = self._login_expert_headers()
        marker = f"invalid-path-{uuid.uuid4().hex}"
        suggestion_id = self._upload_and_approve(headers=headers, marker=marker)

        response = self.client.post(
            f"/workflow/suggestions/{suggestion_id}/apply",
            headers=headers,
            json={"kb_path": "../outside.md"},
        )

        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn("kb_path", response.text)

    def test_apply_rejects_existing_explicit_kb_path(self) -> None:
        headers = self._login_expert_headers()
        marker = f"conflict-{uuid.uuid4().hex}"
        suggestion_id = self._upload_and_approve(headers=headers, marker=marker)

        rel_kb_path = f"test-artifacts/{marker}.md"
        existing_file = (self._kb_root / rel_kb_path).resolve()
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("already exists\n", encoding="utf-8")
        self._created_kb_files.append(existing_file)

        with patch("app.routers.workflow._reindex_kb_to_chroma", return_value=None):
            response = self.client.post(
                f"/workflow/suggestions/{suggestion_id}/apply",
                headers=headers,
                json={"kb_path": rel_kb_path},
            )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("already exists", response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
