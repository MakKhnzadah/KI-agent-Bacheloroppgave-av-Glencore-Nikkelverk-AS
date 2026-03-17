from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.kb.html_builder import build_kb_html


router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.post("/build-html")
def build_html() -> dict:
    try:
        stats = build_kb_html()
        return {
            "status": "ok",
            "files": stats.files,
            "output_dir": str(stats.output_dir),
            "index_file": str(stats.index_file),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
