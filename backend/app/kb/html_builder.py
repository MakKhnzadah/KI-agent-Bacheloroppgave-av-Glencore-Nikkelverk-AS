from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import markdown
import yaml
from yaml import YAMLError

from app.vector_store.config import _repo_root_from_here


@dataclass(frozen=True)
class BuildHtmlStats:
    files: int
    output_dir: Path
    index_file: Path


def _split_front_matter(text: str) -> tuple[dict, str]:
    doc = (text or "").lstrip("\ufeff")
    if not doc.startswith("---\n"):
        return {}, text

    lines = doc.splitlines(keepends=True)
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text

    front_raw = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :]).lstrip("\n")

    try:
        parsed = yaml.safe_load(front_raw) or {}
        return (parsed if isinstance(parsed, dict) else {}), body
    except YAMLError:
        return {}, text


def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_html(*, title: str, markdown_body: str) -> str:
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"], output_format="html5")
    body_html = md.convert(markdown_body or "")

    # Minimal HTML with MathJax for LaTeX support.
    return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{title}</title>
    <script>
      window.MathJax = {{
        tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']] }},
        svg: {{ fontCache: 'global' }}
      }};
    </script>
    <script src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js\" defer></script>
  </head>
  <body>
    {body}
  </body>
</html>
""".format(title=_escape_html(title or "Knowledge Base"), body=body_html)


def build_kb_html(*, raw_root: Path | None = None, html_root: Path | None = None) -> BuildHtmlStats:
    repo_root = _repo_root_from_here()
    raw_root = raw_root or (repo_root / "databases" / "knowledge_base" / "raw")
    html_root = html_root or (repo_root / "databases" / "knowledge_base" / "html")

    raw_root = raw_root.resolve()
    html_root.mkdir(parents=True, exist_ok=True)

    pages: list[tuple[str, str]] = []  # (href, title)
    count = 0

    for md_file in sorted(raw_root.rglob("*.md")):
        rel = md_file.relative_to(raw_root)
        out_file = (html_root / rel).with_suffix(".html")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        text = md_file.read_text(encoding="utf-8")
        front, body = _split_front_matter(text)
        title = str(front.get("title") or md_file.stem)
        html = _render_html(title=title, markdown_body=body)
        out_file.write_text(html, encoding="utf-8")

        pages.append((out_file.relative_to(html_root).as_posix(), title))
        count += 1

    index_items = "\n".join(
        f"<li><a href=\"{href}\">{_escape_html(title)}</a></li>" for href, title in pages
    )
    index_html = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Knowledge Base</title>
  </head>
  <body>
    <h1>Knowledge Base</h1>
    <ul>
      {items}
    </ul>
  </body>
</html>
""".format(items=index_items)

    index_file = html_root / "index.html"
    index_file.write_text(index_html, encoding="utf-8")

    return BuildHtmlStats(files=count, output_dir=html_root, index_file=index_file)
