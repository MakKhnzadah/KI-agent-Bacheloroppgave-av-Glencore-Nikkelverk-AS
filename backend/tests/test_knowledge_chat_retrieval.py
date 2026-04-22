from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class KnowledgeChatRetrievalTests(unittest.TestCase):
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
            pass

    def test_knowledge_chat_falls_back_to_lexical_when_vector_unavailable(self) -> None:
        from app.kb.kb_reader import KbDoc

        lexical_docs = [
            KbDoc(
                kb_path="test-artifacts/fallback.md",
                title="Fallback Test",
                category="Sikkerhet",
                author="Test",
                date="2026-03-31",
                content="# Fallback Test\n\nDette er fallback-innhold.",
            )
        ]

        with (
            patch("app.routers.ai_agent._vector_retrieve", return_value=([], [], "Vector disabled")),
            patch("app.kb.kb_reader.search_kb", return_value=lexical_docs),
            patch("app.routers.ai_agent.llm.generate", return_value="Svar fra testmodell"),
        ):
            response = self.client.post(
                "/agent/knowledge-chat",
                json={"message": "Hva sier fallback?", "category": "Sikkerhet"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["answer"], "Svar fra testmodell")
        self.assertGreaterEqual(len(body["sources"]), 1)
        self.assertEqual(body["sources"][0]["retrievalMethod"], "lexical")

    def test_knowledge_chat_prefers_vector_sources_when_available(self) -> None:
        from app.routers.ai_agent import KnowledgeSource

        vector_sources = [
            KnowledgeSource(
                id="kb/vector-source.md",
                title="Vector Source",
                author="System",
                date="2026-03-31",
                category="Vedlikehold",
                retrievalMethod="vector",
            )
        ]
        vector_excerpts = [
            "KILDE: Vector Source\nPATH: kb/vector-source.md\nKATEGORI: Vedlikehold\nMETODE: vector\nUTDRAG:\nChunk"
        ]

        with (
            patch("app.routers.ai_agent._vector_retrieve", return_value=(vector_sources, vector_excerpts, None)),
            patch("app.kb.kb_reader.search_kb", return_value=[]),
            patch("app.routers.ai_agent.llm.generate", return_value="Svar med vector-kilde"),
        ):
            response = self.client.post(
                "/agent/knowledge-chat",
                json={"message": "Hva sier vector?", "category": "Vedlikehold"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["answer"], "Svar med vector-kilde")
        self.assertGreaterEqual(len(body["sources"]), 1)
        self.assertEqual(body["sources"][0]["retrievalMethod"], "vector")


if __name__ == "__main__":
    unittest.main(verbosity=2)
