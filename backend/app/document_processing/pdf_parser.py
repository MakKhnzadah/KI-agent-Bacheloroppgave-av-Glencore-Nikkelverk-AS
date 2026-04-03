import io
import re

import pdfplumber


_PUA_RE = re.compile(r"[\uE000-\uF8FF]")


def _space_ratio(s: str) -> float:
    if not s:
        return 0.0
    return s.count(" ") / max(1, len(s))


def _looks_like_glued_text(s: str) -> bool:
    """Heuristic: PDF extractors sometimes return text with very few spaces."""

    if not s:
        return False

    sample = re.sub(r"\s+", " ", s).strip()
    if len(sample) < 400:
        return False

    words = [w for w in sample.split(" ") if w]
    if not words:
        return False

    avg_len = sum(len(w) for w in words) / len(words)
    long_tokens = sum(1 for w in words if len(w) >= 40)

    return long_tokens >= 8 or (_space_ratio(sample) < 0.055 and avg_len > 11)


def _normalize_pdf_text(text: str) -> str:
    if not text:
        return ""

    s = text.replace("\r\n", "\n")

    # Fix common private-use glyph issues in URLs like "hps" -> "https".
    s = re.sub(r"h[\uE000-\uF8FF]ps://", "https://", s, flags=re.IGNORECASE)
    s = re.sub(r"h[\uE000-\uF8FF]p://", "http://", s, flags=re.IGNORECASE)
    s = re.sub(r"www\.[\uE000-\uF8FF]", "www.", s, flags=re.IGNORECASE)
    s = _PUA_RE.sub("", s)

    # De-hyphenate when a word is broken across a line break.
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)

    # Normalize whitespace while preserving paragraph breaks.
    s = re.sub(r"[ \t\f\v]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    blocks = [b.strip() for b in s.split("\n\n") if b.strip()]
    cleaned_blocks: list[str] = []
    for b in blocks:
        # Within a paragraph, turn single newlines into spaces.
        b2 = re.sub(r"\n+", " ", b)
        b2 = re.sub(r"\s{2,}", " ", b2).strip()
        if b2:
            cleaned_blocks.append(b2)

    return "\n\n".join(cleaned_blocks).strip()


def pdf_parser(content: bytes) -> str:
    pages_text: list[str] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            extracted_candidates: list[str] = []
            # Try a few extraction strategies; different PDFs respond to different params.
            for kwargs in (
                {"x_tolerance": 2, "y_tolerance": 3},
                {},
                {"layout": True},
            ):
                try:
                    t = page.extract_text(**kwargs) if kwargs else page.extract_text()
                except TypeError:
                    # Older pdfplumber/pdfminer versions might not support some kwargs.
                    continue
                if t:
                    extracted_candidates.append(t)

            extracted = max(extracted_candidates, key=len, default="")

            # If the extractor returns “glued” text, fall back to word extraction.
            if not extracted or _looks_like_glued_text(extracted):
                try:
                    words = page.extract_words(
                        keep_blank_chars=False,
                        use_text_flow=True,
                    )
                    extracted = " ".join((w.get("text") or "").strip() for w in words if (w.get("text") or "").strip())
                except Exception:
                    # Keep the original extracted (even if empty); downstream can still handle.
                    pass

            extracted = extracted.strip()
            if extracted:
                pages_text.append(extracted)

    return _normalize_pdf_text("\n\n".join(pages_text))