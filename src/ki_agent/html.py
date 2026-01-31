from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter
import markdown as md
from jinja2 import Template


PAGE_TEMPLATE = Template(
    """<!doctype html>
<html lang="no">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }}</title>
  <style>
    body { font-family: system-ui, Segoe UI, Roboto, Arial, sans-serif; margin: 2rem; max-width: 900px; }
    pre { background: #f6f8fa; padding: 1rem; overflow: auto; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    a { color: #0969da; }
  </style>
</head>
<body>
  <nav><a href="index.html">Index</a></nav>
  <h1>{{ title }}</h1>
  <article>{{ body|safe }}</article>
</body>
</html>"""
)


INDEX_TEMPLATE = Template(
    """<!doctype html>
<html lang="no">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kunnskapsbank</title>
</head>
<body>
  <h1>Kunnskapsbank</h1>
  <ul>
    {% for page in pages %}
      <li><a href="{{ page.filename }}">{{ page.title }}</a></li>
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
