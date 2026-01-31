from __future__ import annotations

from pathlib import Path

import frontmatter

from .models import ReviewedSuggestion, ReviewDecision
from .storage import list_files, read_json


def _append_section(md_path: Path, section_md: str) -> None:
    post = frontmatter.load(str(md_path))
    body = (post.content or "").rstrip() + "\n\n" + section_md.strip() + "\n"
    post.content = body
    md_path.write_text(frontmatter.dumps(post), encoding="utf-8")


def apply_approved(reviews_dir: Path) -> list[Path]:
    review_files = list_files(reviews_dir, ".review.json")
    if not review_files:
        raise RuntimeError("No reviews found. Run `ki-agent review` first.")

    changed: list[Path] = []
    for review_file in review_files:
        reviewed = read_json(ReviewedSuggestion, review_file)
        if reviewed.decision != ReviewDecision.approved:
            continue

        target = Path(reviewed.suggestion.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if reviewed.suggestion.operation.value == "append_section":
            _append_section(target, reviewed.suggestion.proposed_markdown)
            changed.append(target)
        else:
            raise NotImplementedError(f"Operation not implemented in MVP: {reviewed.suggestion.operation}")

    return changed
