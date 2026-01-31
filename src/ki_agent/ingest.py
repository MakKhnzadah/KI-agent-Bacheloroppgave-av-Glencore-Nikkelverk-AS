from __future__ import annotations

from pathlib import Path

from .config import Settings
from .storage import ensure_dir


SUPPORTED_SUFFIXES = {".txt", ".md"}


def ingest_inputs(settings: Settings, input_dir: Path) -> list[Path]:
    """MVP ingest: accepts .txt/.md only.

    For PDF/Office/email, add parsers later (e.g. pypdf, python-docx, msg-extractor).
    """

    ensure_dir(settings.uploads_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")

    uploaded: list[Path] = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        target = settings.uploads_dir / path.name
        target.write_bytes(path.read_bytes())
        uploaded.append(target)

    return uploaded
