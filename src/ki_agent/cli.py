from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.pretty import Pretty

from .apply import apply_approved
from .config import get_settings
from .html import build_html
from .ingest import ingest_inputs
from .kb_vector import index_knowledge_base, search_knowledge_base
from .normalize import normalize_uploads
from .review import review_suggestions
from .suggest import generate_suggestions

app = typer.Typer(add_completion=False, help="KI-agent pipeline (MVP)")
console = Console()


@app.command()
def ingest(input_dir: Path = typer.Argument(..., exists=False, help="Directory with input docs")):
    settings = get_settings()
    uploaded = ingest_inputs(settings, input_dir)
    console.print(f"Uploaded {len(uploaded)} file(s) to {settings.uploads_dir}")


@app.command()
def normalize():
    settings = get_settings()
    outputs = normalize_uploads(settings)
    console.print(f"Normalized {len(outputs)} file(s) to {settings.normalized_dir}")


@app.command()
def suggest():
    settings = get_settings()
    out = generate_suggestions(settings)
    console.print(f"Generated {len(out)} suggestion(s) in {settings.suggestions_dir}")


@app.command()
def review(reviewer: str | None = typer.Option(None, help="Reviewer name/identifier")):
    settings = get_settings()
    out = review_suggestions(settings.suggestions_dir, settings.reviews_dir, reviewer=reviewer)
    console.print(f"Wrote {len(out)} review decision(s) to {settings.reviews_dir}")


@app.command()
def apply():
    settings = get_settings()
    changed = apply_approved(settings.reviews_dir)
    console.print(f"Applied {len(changed)} approved change(s)")


@app.command(name="build-html")
def build_html_cmd():
    settings = get_settings()
    outputs = build_html(settings.kb_raw_dir, settings.kb_html_dir)
    console.print(f"Built {len(outputs)} HTML file(s) in {settings.kb_html_dir}")


@app.command(name="index-kb")
def index_kb_cmd():
    """Index the knowledge base into the configured vector database."""

    settings = get_settings()
    count = index_knowledge_base(settings)
    console.print(f"Indexed {count} chunk(s) into vector store ({settings.vector_provider}).")


@app.command(name="search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(5, min=1, max=20, help="Number of results"),
):
    """Semantic search over the indexed knowledge base."""

    settings = get_settings()
    results = search_knowledge_base(settings, query=query, top_k=top_k)
    console.print(Pretty(results, expand_all=False))


if __name__ == "__main__":
    app()
