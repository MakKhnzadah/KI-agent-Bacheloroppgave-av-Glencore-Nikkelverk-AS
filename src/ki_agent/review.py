from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .models import ReviewedSuggestion, ReviewDecision, Suggestion
from .storage import ensure_dir, list_files, read_json, write_json

console = Console()


def review_suggestions(suggestions_dir: Path, reviews_dir: Path, reviewer: str | None = None) -> list[Path]:
    ensure_dir(reviews_dir)

    suggestion_files = list_files(suggestions_dir, ".suggestion.json")
    if not suggestion_files:
        raise RuntimeError("No suggestions found. Run `ki-agent suggest` first.")

    outputs: list[Path] = []
    for path in suggestion_files:
        suggestion = read_json(Suggestion, path)

        console.rule(f"Suggestion {suggestion.suggestion_id}")
        console.print(f"Target: {suggestion.target_path}")
        console.print(f"Operation: {suggestion.operation}")
        console.print(f"Rationale: {suggestion.rationale}")
        console.print("\nProposed markdown:\n")
        console.print(suggestion.proposed_markdown)

        choice = console.input("\nApprove? (y/n) ").strip().lower()
        decision = ReviewDecision.approved if choice in {"y", "yes"} else ReviewDecision.rejected

        reviewed = ReviewedSuggestion(suggestion=suggestion, decision=decision, reviewer=reviewer)
        out = reviews_dir / f"{suggestion.suggestion_id}.review.json"
        write_json(reviewed, out)
        outputs.append(out)

    return outputs
