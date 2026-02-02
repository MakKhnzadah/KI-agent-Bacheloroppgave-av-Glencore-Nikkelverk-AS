from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .pipeline import (
    apply_approved,
    build_html,
    generate_suggestions,
    get_settings,
    ingest_inputs,
    normalize_uploads,
    review_suggestions,
)

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


if __name__ == "__main__":
    app()
