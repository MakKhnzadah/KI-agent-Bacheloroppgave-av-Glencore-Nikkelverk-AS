from __future__ import annotations

import re
from pathlib import Path

from .config import Settings
from .storage import ensure_dir


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def normalize_uploads(settings: Settings) -> list[Path]:
    ensure_dir(settings.normalized_dir)

    outputs: list[Path] = []
    for src in sorted(settings.uploads_dir.glob("*")):
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8", errors="ignore")
        normalized = normalize_text(text)
        out = settings.normalized_dir / f"{src.stem}.normalized.txt"
        out.write_text(normalized, encoding="utf-8")
        outputs.append(out)

    return outputs
