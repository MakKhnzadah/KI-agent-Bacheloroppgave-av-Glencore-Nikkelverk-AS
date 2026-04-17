from __future__ import annotations


def render_markdown_with_frontmatter(
    *,
    title: str,
    body: str,
    category: str = "Annet",
    review_status: str = "pending",
    confidence_score: float = 0.0,
    tags: list[str] | None = None,
) -> str:
    safe_title = (title or "Untitled").replace('"', "'")
    tags = tags or []

    return (
        "---\n"
        f"title: \"{safe_title}\"\n"
        f"tags: {tags}\n"
        f"category: \"{category}\"\n"
        f"review_status: \"{review_status}\"\n"
        f"confidence_score: {float(confidence_score)}\n"
        "---\n\n"
        + body
    )
