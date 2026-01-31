from __future__ import annotations

from pathlib import Path

import frontmatter

from .chunking import chunk_text
from .config import Settings
from .embeddings import embed_texts
from .vectorstore import VectorChunk, get_vectorstore, make_chunk_id


def index_knowledge_base(settings: Settings, *, kb_dir: Path | None = None) -> int:
    """Index Markdown knowledge base files into the configured vector store."""

    kb_dir = kb_dir or settings.kb_raw_dir

    vectorstore = get_vectorstore(settings)

    all_chunks: list[VectorChunk] = []
    all_texts: list[str] = []

    for md_path in sorted(kb_dir.glob("*.md")):
        post = frontmatter.load(str(md_path))
        title = post.get("title") or md_path.stem
        body = post.content or ""

        chunks = chunk_text(body)
        for idx, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(str(md_path.as_posix()), idx)
            meta = {
                "source_path": str(md_path.as_posix()),
                "title": str(title),
                "chunk_index": idx,
            }
            all_chunks.append(VectorChunk(chunk_id=chunk_id, text=chunk, metadata=meta))
            all_texts.append(chunk)

    embeddings = embed_texts(settings, all_texts) if all_texts else []
    vectorstore.upsert(chunks=all_chunks, embeddings=embeddings)

    return len(all_chunks)


def search_knowledge_base(settings: Settings, *, query: str, top_k: int = 5) -> list[dict]:
    """Semantic search over the indexed knowledge base."""

    vectorstore = get_vectorstore(settings)
    [query_vec] = embed_texts(settings, [query])
    results = vectorstore.query(embedding=query_vec, n_results=top_k)

    return [
        {
            "chunk_id": r.chunk_id,
            "distance": r.distance,
            "text": r.text,
            "metadata": r.metadata,
        }
        for r in results
    ]
