from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class ViewerReadOnlyAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory(prefix="workflow-db-")
        cls._db_path = Path(cls._tmp_dir.name) / "workflow.sqlite3"
        os.environ["WORKFLOW_DB_PATH"] = str(cls._db_path)

        from app.main import app

        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_cm.__exit__(None, None, None)
        try:
            cls._tmp_dir.cleanup()
        except PermissionError:
            pass

    def _login(self, *, email: str, password: str) -> dict:
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _upload_txt_document(self, token: str, filename: str = "viewer-authz.txt") -> str:
        response = self.client.post(
            "/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, b"Dette er en enkel testfil for authz.", "text/plain")},
            data={"category": "Kvalitet"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("suggestion_id", payload)
        return payload["suggestion_id"]

    def test_employee_has_read_access_to_dashboard_data_sources(self) -> None:
        viewer = self._login(email="viewer@glencore.com", password="viewer123")
        headers = {"Authorization": f"Bearer {viewer['accessToken']}"}

        kb_stats = self.client.get("/workflow/kb/stats", headers=headers)
        kb_docs = self.client.get("/workflow/kb/documents?limit=5&offset=0", headers=headers)
        activities = self.client.get("/api/activities?limit=5", headers=headers)

        self.assertEqual(kb_stats.status_code, 200, kb_stats.text)
        self.assertEqual(kb_docs.status_code, 200, kb_docs.text)
        self.assertEqual(activities.status_code, 200, activities.text)

    def test_employee_cannot_mutate_workflow_or_kb(self) -> None:
        expert = self._login(email="expert@glencore.com", password="admin123")
        viewer = self._login(email="viewer@glencore.com", password="viewer123")

        suggestion_id = self._upload_txt_document(expert["accessToken"])
        viewer_headers = {"Authorization": f"Bearer {viewer['accessToken']}"}

        similarity = self.client.get(f"/workflow/suggestions/{suggestion_id}/similarity", headers=viewer_headers)
        delete_suggestion = self.client.delete(f"/workflow/suggestions/{suggestion_id}", headers=viewer_headers)
        report_issue = self.client.post(
            "/workflow/kb/issues",
            headers=viewer_headers,
            json={
                "kb_path": "procedures/example.md",
                "message": "Dette er en testmelding for authz-kontroll.",
            },
        )

        self.assertEqual(similarity.status_code, 403, similarity.text)
        self.assertEqual(delete_suggestion.status_code, 403, delete_suggestion.text)
        self.assertEqual(report_issue.status_code, 403, report_issue.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
