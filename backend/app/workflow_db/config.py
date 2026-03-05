from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkflowDbConfig:
    db_path: Path


def _repo_root_from_here() -> Path:
    # backend/app/workflow_db/config.py -> repo root is 3 parents up
    return Path(__file__).resolve().parents[3]


def get_repo_root() -> Path:
    return _repo_root_from_here()


def load_workflow_db_config() -> WorkflowDbConfig:
    repo_root = _repo_root_from_here()
    default_path = repo_root / "databases" / "workflow" / "workflow.sqlite3"

    return WorkflowDbConfig(
        db_path=Path(os.getenv("WORKFLOW_DB_PATH", str(default_path))),
    )
