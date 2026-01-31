from __future__ import annotations

import uuid
from pathlib import Path

from .config import Settings
from .models import Citation, Suggestion, SuggestionOperation
from .storage import ensure_dir, list_files, write_json


def _heuristic_suggestion(target_path: str, normalized_paths: list[Path]) -> Suggestion:
    joined = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in normalized_paths[:3])
    excerpt = joined[:1200].strip()
    proposed = (
        "## Utkast fra nye kilder\n\n"
        "Dette er et MVP-utkast (heuristisk) basert på opplastede dokumenter.\n\n"
        "### Ekstrakt\n\n"
        f"```\n{excerpt}\n```\n"
    )

    citations = [Citation(source_name=p.name) for p in normalized_paths]

    return Suggestion(
        suggestion_id=str(uuid.uuid4()),
        target_path=target_path,
        operation=SuggestionOperation.append_section,
        proposed_markdown=proposed,
        rationale="Heuristisk forslag (ingen LLM konfigurert).",
        citations=citations,
    )


def generate_suggestions(settings: Settings) -> list[Path]:
    """Generate suggestions and store them as JSON.

    MVP uses a heuristic if no LLM is configured.
    """

    ensure_dir(settings.suggestions_dir)

    normalized_paths = list_files(settings.normalized_dir, ".txt")
    if not normalized_paths:
        raise RuntimeError("No normalized files found. Run `ki-agent ingest` then `ki-agent normalize` first.")

    # For MVP we always suggest appending to the example doc.
    target_path = str((settings.kb_raw_dir / "example-prosess.md").as_posix())

    suggestion = _heuristic_suggestion(target_path=target_path, normalized_paths=normalized_paths)

    out = settings.suggestions_dir / f"{suggestion.suggestion_id}.suggestion.json"
    write_json(suggestion, out)

    return [out]
