from __future__ import annotations


def chunk_text(text: str, *, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Chunk text for embedding.

    This is a simple character-based chunker (MVP). For production quality, replace
    with token-based chunking (e.g., tiktoken) and smarter sentence/heading splits.
    """

    cleaned = (text or "").strip()
    if not cleaned:
        return []

    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= max_chars:
        raise ValueError("overlap must be < max_chars")

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)

    return chunks
