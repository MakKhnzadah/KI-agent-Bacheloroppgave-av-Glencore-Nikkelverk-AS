from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional

import yaml
from yaml import YAMLError

from app.vector_store.config import _repo_root_from_here


_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)


@dataclass(frozen=True)
class KbDoc:
    kb_path: str
    title: str
    category: str
    author: str
    date: str
    content: str


def kb_raw_root() -> Path:
    repo_root = _repo_root_from_here()
    return Path(repo_root) / "databases" / "knowledge_base" / "raw"


def resolve_kb_path(kb_path: str) -> Path:
    root = kb_raw_root().resolve()
    rel = Path(kb_path)
    rel = Path(*rel.parts)
    if rel.is_absolute():
        raise ValueError("kb_path must be relative")

    full = (root / rel).resolve()
    if root not in full.parents and full != root:
        raise ValueError("kb_path escapes KB root")
    if full.suffix.lower() != ".md":
        raise ValueError("kb_path must end with .md")
    return full


def iter_kb_markdown_files() -> list[Path]:
    root = kb_raw_root()
    if not root.exists():
        return []

    files: list[Path] = []
    for p in root.rglob("*.md"):
        name = p.name.lower()
        if name in {"readme.md", "_template.md"}:
            continue
        if p.name.startswith("_"):
            continue
        files.append(p)

    files.sort(key=lambda x: str(x).lower())
    return files


def read_text_best_effort(path: Path, *, max_chars: int = 300_000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    if len(text) > max_chars:
        return text[:max_chars]
    return text


def split_front_matter(doc: str) -> tuple[dict, str]:
    """Parse YAML front matter if present; returns (frontmatter_dict, body)."""

    text = (doc or "").lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}, doc

    lines = text.splitlines(keepends=True)
    if not lines or lines[0] != "---\n":
        return {}, doc

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, doc

    front_raw = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :]).lstrip("\n")

    def parse(raw: str) -> dict:
        parsed = yaml.safe_load(raw) or {}
        return parsed if isinstance(parsed, dict) else {}

    try:
        return parse(front_raw), body
    except YAMLError:
        # Minimal repair for common YAML pitfalls in title fields.
        repaired_lines: list[str] = []
        for line in front_raw.splitlines():
            if line.startswith("title:"):
                value = line[len("title:") :].strip()
                if value and not (value.startswith('"') or value.startswith("'")) and ":" in value:
                    safe = value.replace("\\", "\\\\").replace('"', "\\\"")
                    repaired_lines.append(f'title: "{safe}"')
                    continue
            repaired_lines.append(line)

        repaired = "\n".join(repaired_lines) + ("\n" if front_raw.endswith("\n") else "")
        try:
            return parse(repaired), body
        except YAMLError:
            return {}, doc


def _normalize_category(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""

    low = v.lower()
    if low in {"prosess", "prosesser", "process", "processes"}:
        return "Prosesser"
    if low in {"sikkerhet", "security"}:
        return "Sikkerhet"
    if low in {"vedlikehold", "maintenance"}:
        return "Vedlikehold"
    if low in {"miljø", "miljo", "environment"}:
        return "Miljø"
    if low in {"kvalitet", "quality"}:
        return "Kvalitet"

    return v[:1].upper() + v[1:]


def doc_metadata(markdown: str, *, kb_path: str) -> tuple[str, str, str, str, str]:
    front, body = split_front_matter(markdown)

    title = ""
    category = ""
    author = ""
    date = ""

    if isinstance(front, dict):
        maybe_title = front.get("title") or front.get("id")
        if isinstance(maybe_title, str):
            title = maybe_title.strip()

        maybe_category = front.get("category") or front.get("kategori")
        if isinstance(maybe_category, str):
            category = _normalize_category(maybe_category)

        maybe_author = front.get("author") or front.get("forfatter")
        if isinstance(maybe_author, str):
            author = maybe_author.strip()

        maybe_date = front.get("date") or front.get("dato")
        if isinstance(maybe_date, str):
            date = maybe_date.strip()

    if not title:
        # Try first markdown heading.
        m = re.search(r"(?m)^#\s+(.+)$", markdown)
        if m:
            title = m.group(1).strip()

    if not title:
        title = Path(kb_path).stem

    if not category:
        # Try to infer from path segments.
        parts = Path(kb_path).parts
        if parts:
            category = _normalize_category(parts[0].replace("-", " "))

    return title, category or "Annet", author or "Kunnskapsbank", date or ""


def get_kb_doc(kb_path: str) -> KbDoc:
    full = resolve_kb_path(kb_path)
    raw = read_text_best_effort(full)
    title, category, author, date = doc_metadata(raw, kb_path=kb_path)
    return KbDoc(
        kb_path=kb_path,
        title=title,
        category=category,
        author=author,
        date=date,
        content=raw,
    )


def kb_stats(categories: Optional[list[str]] = None) -> tuple[int, dict[str, int]]:
    files = iter_kb_markdown_files()
    by_cat: dict[str, int] = {}
    total = 0

    for p in files:
        total += 1
        rel = p.resolve().relative_to(kb_raw_root().resolve()).as_posix()
        try:
            raw = read_text_best_effort(p, max_chars=60_000)
        except OSError:
            continue
        _, cat, _, _ = doc_metadata(raw, kb_path=rel)
        by_cat[cat] = by_cat.get(cat, 0) + 1

    if categories:
        filtered = {cat: by_cat.get(cat, 0) for cat in categories}
        return total, filtered

    return total, by_cat


def _tokenize(text: str, *, max_tokens: int = 128) -> list[str]:
    tokens = _WORD_RE.findall((text or "").lower())
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
    return tokens


def search_kb(query: str, *, category: Optional[str] = None, limit: int = 3) -> list[KbDoc]:
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    wanted_cat = _normalize_category(category) if category and category != "All" else ""

    scored: list[tuple[int, KbDoc]] = []
    root = kb_raw_root().resolve()

    for p in iter_kb_markdown_files():
        try:
            raw = read_text_best_effort(p, max_chars=200_000)
        except OSError:
            continue

        rel = p.resolve().relative_to(root).as_posix()
        title, cat, author, date = doc_metadata(raw, kb_path=rel)
        if wanted_cat and cat != wanted_cat:
            continue

        front, body = split_front_matter(raw)
        hay = f"{title}\n\n{body}" if isinstance(front, dict) else raw
        hay_low = hay.lower()

        score = 0
        for tok in q_tokens:
            if not tok:
                continue
            if tok in (title or "").lower():
                score += 6
            # cheap term match count in a limited window
            score += min(10, hay_low.count(tok))

        if score <= 0:
            continue

        snippet = (body or "").strip()[:1200]
        content = raw
        scored.append(
            (
                score,
                KbDoc(
                    kb_path=rel,
                    title=title,
                    category=cat,
                    author=author,
                    date=date,
                    content=content,
                ),
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[: max(1, limit)]]
