from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import frontmatter
import markdown as md
from jinja2 import Template
from rich.console import Console

from pydantic_settings import BaseSettings, SettingsConfigDict

from .models.schemas import Citation, ReviewedSuggestion, ReviewDecision, Suggestion, SuggestionOperation
from .storage import ensure_dir, list_files, read_json, write_json

console = Console()

SUPPORTED_SUFFIXES = {".txt", ".md"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Optional (future): API key if/when you add an LLM call.
    openai_api_key: str | None = None

    kb_raw_dir: Path = Path("databases/knowledge_base/raw")
    kb_html_dir: Path = Path("databases/knowledge_base/html")
    data_dir: Path = Path("databases/data")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def normalized_dir(self) -> Path:
        return self.data_dir / "normalized"

    @property
    def suggestions_dir(self) -> Path:
        return self.data_dir / "suggestions"

    @property
    def reviews_dir(self) -> Path:
        return self.data_dir / "reviews"


def get_settings() -> Settings:
    return Settings()


def ingest_inputs(settings: Settings, input_dir: Path) -> list[Path]:
    """MVP ingest: accepts .txt/.md only."""

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
    ensure_dir(settings.suggestions_dir)

    normalized_paths = list_files(settings.normalized_dir, ".txt")
    if not normalized_paths:
        raise RuntimeError("No normalized files found. Run `ki-agent ingest` then `ki-agent normalize` first.")

    target_path = str((settings.kb_raw_dir / "example-prosess.md").as_posix())
    suggestion = _heuristic_suggestion(target_path=target_path, normalized_paths=normalized_paths)

    out = settings.suggestions_dir / f"{suggestion.suggestion_id}.suggestion.json"
    write_json(suggestion, out)
    return [out]


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


PAGE_TEMPLATE = Template(
    """<!doctype html>
<html lang=\"no\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{{ title }}</title>
  <style>
    body { font-family: system-ui, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; max-width: 900px; }
    pre { background: #f6f8fa; padding: 1rem; overflow: auto; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    a { color: #0969da; }
  </style>
</head>
<body>
  <nav><a href=\"index.html\">Index</a></nav>
  <h1>{{ title }}</h1>
  <article>{{ body|safe }}</article>
</body>
</html>"""
)


INDEX_TEMPLATE = Template(
    """<!doctype html>
<html lang=\"no\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Kunnskapsbank</title>
</head>
<body>
  <h1>Kunnskapsbank</h1>
  <ul>
    {% for page in pages %}
      <li><a href=\"{{ page.filename }}\">{{ page.title }}</a></li>
    {% endfor %}
  </ul>
</body>
</html>"""
)


@dataclass
class Page:
    filename: str
    title: str


def build_html(kb_raw_dir: Path, kb_html_dir: Path) -> list[Path]:
    kb_html_dir.mkdir(parents=True, exist_ok=True)

    pages: list[Page] = []
    outputs: list[Path] = []

    for md_path in sorted(kb_raw_dir.glob("*.md")):
        post = frontmatter.load(str(md_path))
        title = post.get("title") or md_path.stem

        html_body = md.markdown(post.content or "", extensions=["fenced_code", "tables"])
        page_html = PAGE_TEMPLATE.render(title=title, body=html_body)

        out = kb_html_dir / f"{md_path.stem}.html"
        out.write_text(page_html, encoding="utf-8")
        outputs.append(out)
        pages.append(Page(filename=out.name, title=str(title)))

    index_html = INDEX_TEMPLATE.render(pages=pages)
    index_path = kb_html_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    outputs.append(index_path)

    return outputs
