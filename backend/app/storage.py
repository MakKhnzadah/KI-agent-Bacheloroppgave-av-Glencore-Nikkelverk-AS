from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(model: BaseModel, path: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def read_json(model_type: type[T], path: Path) -> T:
    # Accept UTF-8 with or without BOM (Windows tools may emit BOM).
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return model_type.model_validate(data)


def list_files(dir_path: Path, suffix: str) -> list[Path]:
    if not dir_path.exists():
        return []
    return sorted([p for p in dir_path.rglob(f"*{suffix}") if p.is_file()])
