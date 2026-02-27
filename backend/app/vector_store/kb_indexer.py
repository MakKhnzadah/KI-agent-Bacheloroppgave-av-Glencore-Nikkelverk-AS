from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

from .chroma_store import ChromaVectorStore
from .config import _repo_root_from_here
from .ollama_embeddings import OllamaEmbeddingClient


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_markdown_with_front_matter(path: Path) -> Tuple[Dict[str, Any], str]:
    content = path.read_text(encoding="utf-8")

    if content.startswith("---\n"):
        parts = content.split("---\n", 2)
        # parts: ["", frontmatter, rest]
        if len(parts) == 3:
            front = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return dict(front), body

    return {}, content


def _chunk_markdown(text: str, *, max_chars: int = 2400, overlap_chars: int = 200) -> List[str]:
    # Simple and robust chunker:
    # 1) split by headings
    # 2) then pack into <= max_chars windows with overlap
    lines = text.splitlines()
    sections: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            sections.append("\n".join(buf).strip())
            buf = []

    for line in lines:
        if line.startswith("#") and buf:
            flush()
        buf.append(line)
    flush()

    windows: List[str] = []
    for section in sections:
        s = section.strip()
        if not s:
            continue
        if len(s) <= max_chars:
            windows.append(s)
            continue

        start = 0
        while start < len(s):
            end = min(len(s), start + max_chars)
            windows.append(s[start:end])
            if end >= len(s):
                break
            start = max(0, end - overlap_chars)

    return windows


def iter_kb_markdown_files(kb_raw_dir: Optional[Path] = None) -> Iterable[Path]:
    repo_root = _repo_root_from_here()
    root = kb_raw_dir or (repo_root / "databases" / "knowledge_base" / "raw")
    if not root.exists():
        return []

    for path in root.rglob("*.md"):
        if path.name.startswith("_"):
            continue
        yield path


def build_chunks_for_file(path: Path) -> List[Chunk]:
    front, body = _load_markdown_with_front_matter(path)

    doc_id = str(front.get("id") or path.stem)
    title = str(front.get("title") or path.stem)
    tags_raw = front.get("tags")
    if tags_raw is None:
        tags: List[str] = []
    elif isinstance(tags_raw, list):
        tags = [str(t) for t in tags_raw]
    else:
        tags = [str(tags_raw)]

    # Chroma metadata should be scalar values (strings/numbers/bools).
    tags_str = ",".join(tags)

    body_chunks = _chunk_markdown(body)
    body_hash = _sha256(body)

    chunks: List[Chunk] = []
    for idx, chunk_text in enumerate(body_chunks):
        chunk_id = f"{doc_id}:{idx}"
        metadata: Dict[str, Any] = {
            "doc_id": doc_id,
            "title": title,
            "tags": tags_str,
            "path": str(path.as_posix()),
            "chunk_index": idx,
            "doc_hash": body_hash,
        }
        chunks.append(Chunk(chunk_id=chunk_id, text=chunk_text, metadata=metadata))

    return chunks


def index_kb(
    *,
    store: ChromaVectorStore,
    embedder: OllamaEmbeddingClient,
    kb_raw_dir: Optional[Path] = None,
) -> Dict[str, int]:
    files = list(iter_kb_markdown_files(kb_raw_dir))

    total_chunks = 0
    for path in files:
        chunks = build_chunks_for_file(path)
        if not chunks:
            continue

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        embeddings = [embedder.embed_text(t) for t in documents]

        store.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        total_chunks += len(chunks)

    return {"files": len(files), "chunks": total_chunks}
