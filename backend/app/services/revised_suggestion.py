from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.services.suggestion_postprocess import postprocess_payload_sections as _postprocess_payload_sections
from app.services.suggestion_rendering import render_markdown_with_frontmatter

_ALLOWED_CATEGORIES = {"Sikkerhet", "Vedlikehold", "Miljø", "Kvalitet", "Prosedyre", "Annet"}
_MIN_EXTRACTED_WORDS = 40

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_TOC_HEADING_RE = re.compile(r"^(innhold|innholdsfortegnelse|contents|table\s+of\s+contents)\b", re.IGNORECASE)
_EVIDENCE_RE = re.compile(r"\(KILDE:\s*\"([^\"]{8,220})\"\)\s*$")
_MISSING_MARKER = "(ikke oppgitt i utdraget)"

_SECTION_SHORT = "Kort sammendrag"
_SECTION_KEY = "Viktigste punkter"
_SECTION_CHAPTER = "Kapittelvis sammendrag"
_SECTION_DETAILS = "Relevante detaljer"
_SECTION_ACTIONS = "Eventuelle tiltak / anbefalinger"

def _normalize_for_evidence_match(text: str) -> str:
    """Normalize text for evidence quote matching.

    Keep conservative: collapse whitespace and normalize a few common Unicode
    variants (dashes/quotes) that often differ between extraction and LLM output.
    """

    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash
    t = t.replace("\u201c", '"').replace("\u201d", '"')  # curly double quotes
    t = t.replace("\u2018", "'").replace("\u2019", "'")  # curly single quotes
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:)])", r"\1", t)
    return t


def _is_toc_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    # e.g. "1 Helse og sikkerhet i PA-anlegget 2" or "1.2 Farlige stoffer 2"
    if re.match(r"^\d+(?:\.\d+)*\s+\S+.*\s+\d{1,4}\s*$", s):
        return True
    # roman numeral page markers
    if re.match(r"^\d+(?:\.\d+)*\s+\S+.*\s+[ivxlcdm]{1,6}\s*$", s, flags=re.IGNORECASE):
        return True
    return False


def _looks_like_table_of_contents(text: str) -> bool:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in raw.split("\n") if (ln or "").strip()]
    if not lines:
        return False

    head = lines[:220]
    # Strong signal: explicit heading near the start.
    if any(_TOC_HEADING_RE.match((ln or "").strip()) for ln in head[:40]):
        return True

    # Otherwise, ratio of TOC-like lines in the beginning.
    sample = head[: min(140, len(head))]
    if len(sample) < 10:
        return False
    toc_like = sum(1 for ln in sample if _is_toc_line(ln))
    ratio = toc_like / max(1, len(sample))
    return toc_like >= 8 and ratio >= 0.45


@dataclass(frozen=True)
class GenerationPlan:
    source_words: int
    windows: int
    window_chars: int
    max_source_chars: int
    num_predict: int


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def is_effectively_empty(text: str) -> bool:
    return word_count(text) < _MIN_EXTRACTED_WORDS


def strip_pdf_noise_lines(text: str) -> str:
    lines: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue

        lower = s.lower()
        if "authorized licensed use" in lower:
            continue
        if "downloaded on" in lower and "from ieee xplore" in lower:
            continue
        if "restrictions apply" in lower:
            continue
        if re.fullmatch(r"page\s*\d+", s, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\d{3,}", s):
            continue
        lines.append(s)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def strip_leading_table_of_contents(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    # If it's clearly not a TOC, keep it.
    if not _looks_like_table_of_contents(raw):
        return raw.strip()

    heading_idx: int | None = None
    for i in range(min(len(lines), 220)):
        if _TOC_HEADING_RE.match((lines[i] or "").strip()):
            heading_idx = i
            break

    def strip_after(start_idx: int) -> str:
        toc_indices: list[int] = []
        nonmatch_streak = 0
        for j in range(start_idx, min(len(lines), start_idx + 500)):
            s = (lines[j] or "").strip()
            if not s:
                if toc_indices:
                    nonmatch_streak = 0
                continue
            if _is_toc_line(s):
                toc_indices.append(j)
                nonmatch_streak = 0
                continue
            if toc_indices:
                nonmatch_streak += 1
                if nonmatch_streak >= 6:
                    break
            else:
                nonmatch_streak += 1
                if nonmatch_streak >= 25:
                    break

        # Even short TOCs should be stripped if we have a clear heading.
        if len(toc_indices) < 4:
            return raw.strip()

        drop_start = max(0, start_idx - 1)
        drop_end = toc_indices[-1]
        kept = lines[:drop_start] + lines[drop_end + 1 :]
        return "\n".join(kept).strip()

    if heading_idx is not None:
        return strip_after(heading_idx + 1)

    start_window = lines[:180]
    nonempty = [ln for ln in start_window if (ln or "").strip()]
    if len(nonempty) >= 12:
        toc_like = sum(1 for ln in nonempty if _is_toc_line(ln))
        if toc_like >= 8 and (toc_like / max(1, len(nonempty))) >= 0.45:
            last_toc = 0
            for idx, ln in enumerate(start_window):
                if _is_toc_line(ln):
                    last_toc = idx
            tail = "\n".join(lines[last_toc + 1 :]).strip()
            return tail or raw.strip()

    return raw.strip()


def _extract_toc_entries(text: str, *, max_items: int = 70) -> list[str]:
    """Extract chapter-like entries from a TOC snippet.

    Output is deterministic and grounded: each entry becomes a bullet seed.
    """

    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    out: list[str] = []

    for ln in lines:
        if _TOC_HEADING_RE.match(ln):
            continue
        if not _is_toc_line(ln):
            continue

        # Remove trailing page number / roman numeral.
        cleaned = re.sub(r"\s+[0-9]{1,4}\s*$", "", ln).strip()
        cleaned = re.sub(r"\s+[ivxlcdm]{1,6}\s*$", "", cleaned, flags=re.IGNORECASE).strip()

        # Normalize spacing.
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -\t")
        if not cleaned:
            continue
        out.append(cleaned)
        if len(out) >= max_items:
            break

    # Deduplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for item in out:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def toc_only_structured_draft(original_filename: str, extracted_text: str) -> str:
    """Create a useful structured draft when we only have a table of contents.

    This is intentionally NOT an LLM output to avoid hallucinations.
    """

    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    cleaned = clean_extracted_text(extracted_text)
    entries = _extract_toc_entries(cleaned)
    if not entries:
        return fallback_structured_document_short(original_filename, cleaned)

    chapter_bullets = [f"- {e}: (ikke oppgitt i utdraget)" for e in entries[:60]]
    body = (
        f"# {title}\n\n"
        "## Kort sammendrag\n"
        "- Utdraget ser ut til å være en innholdsfortegnelse. Selve kapittelinnholdet er ikke inkludert i utdraget.\n"
        "- Oppsummering av regler/krav/tiltak kan derfor ikke gjøres uten mer tekst.\n\n"
        "## Viktigste punkter\n"
        "- (ikke oppgitt i utdraget)\n\n"
        "## Kapittelvis sammendrag\n"
        + "\n".join(chapter_bullets)
        + "\n\n"
        "## Relevante detaljer\n"
        "- (ikke oppgitt i utdraget)\n\n"
        "## Eventuelle tiltak / anbefalinger\n"
        "- (ikke oppgitt i utdraget)\n"
    )

    return render_markdown_with_frontmatter(title=safe_title, body=body)


def extract_abstract(text: str, max_chars: int = 2500) -> str | None:
    t = text or ""
    m = re.search(
        r"\b(?:Abstract|Sammendrag|Kort\s+sammendrag)\s*[—\-:]\s*(.+)",
        t,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    after = m.group(1)
    stop = re.search(
        r"\n\s*(Index Terms|Nøkkelord|Noekkelord|Stikkord|I\.|1\.|Introduction|Innledning|Introduksjon)\b",
        after,
        flags=re.IGNORECASE,
    )
    abstract = after[: stop.start()] if stop else after
    abstract = abstract.strip()
    if not abstract:
        return None
    return abstract[:max_chars].strip()


def extract_conclusion(text: str, max_chars: int = 2000) -> str | None:
    t = text or ""
    m = re.search(
        r"\n\s*(?:\d+(?:\.\d+)*\s*)?(?:VI\.|V?I?\.?\s*)?(CONCLUSION|Conclusion|Konklusjon|Oppsummering|Avslutning)\b.*\n",
        t,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    tail = t[m.end() :]
    stop = re.search(r"\n\s*(REFERENCES|References|Referanser|Litteratur|Kilder|Vedlegg)\b", tail, flags=re.IGNORECASE)
    conclusion = tail[: stop.start()] if stop else tail
    conclusion = conclusion.strip()
    if not conclusion:
        return None
    return conclusion[:max_chars].strip()


def clean_extracted_text(text: str) -> str:
    cleaned = strip_pdf_noise_lines(text)
    if not cleaned.strip():
        cleaned = (text or "").strip()
    cleaned = strip_leading_table_of_contents(cleaned)
    cleaned = repair_extraction_artifacts(cleaned)
    return cleaned.strip()


def repair_extraction_artifacts(text: str) -> str:
    """Best-effort cleanup of extraction artifacts.

    Keep conservative: only fix patterns that are very likely artifacts.
    """

    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")

    # Join words that were split by a newline in the middle of a word.
    # Example: "tilgjengeli\ng" -> "tilgjengelig"
    t = re.sub(r"(?m)([A-Za-zÆØÅæøå])\n\s*([a-zæøå])", r"\1\2", t)

    # Insert missing space after a period when a new sentence starts immediately.
    # Example: "tilgjengelig.Løsningen" -> "tilgjengelig. Løsningen"
    t = re.sub(r"([a-zæøå])\.([A-ZÆØÅ])", r"\1. \2", t)

    # Insert missing spaces when a lowercase letter is immediately followed by uppercase/digit.
    # Example: "fraCO2" -> "fra CO2"
    t = re.sub(r"([a-zæøå])([A-ZÆØÅ0-9])", r"\1 \2", t)

    # Common chemistry/unit artifacts from DOCX/PDF extraction.
    # Keep conservative: only normalize well-known patterns.
    t = re.sub(r"\b[Cc]l\s*2\b", "Cl2", t)
    t = re.sub(r"\b[Hh]\s*2\b", "H2", t)
    t = re.sub(r"\b[Oo]\s*2\b", "O2", t)
    t = re.sub(r"\b[Hh]\s*2\s*[Oo]\b", "H2O", t)
    t = re.sub(r"\b[Nn]a\s*OH\b", "NaOH", t)
    t = re.sub(r"\b[Nn]a\s*Cl\b", "NaCl", t)
    t = re.sub(r"\b[Nn]a\s*2\s*SO\s*4\b", "Na2SO4", t)
    t = re.sub(r"\bH\s*2\s*SO\s*4\b", "H2SO4", t)
    t = re.sub(r"\bNi\s*CO\s*3\b", "NiCO3", t)
    t = re.sub(r"\bp\s*H\b", "pH", t)
    t = re.sub(r"\bm\s*V\b", "mV", t)

    # Spacing glitches like "vedca" -> "ved ca".
    t = re.sub(r"\bvedca\b", "ved ca", t, flags=re.IGNORECASE)

    # Reduce excessive blank lines.
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def looks_like_non_norwegian(markdown_or_text: str) -> bool:
    """Heuristic: flag outputs that are mostly English.

    Not a language detector; just catches obvious cases so we can repair/translate.
    """

    body = (markdown_or_text or "").strip()
    if not body:
        return False

    head = body[:5000].lower()
    head = re.sub(r"(?m)^#{1,6}\s+", "", head)
    head = re.sub(r"[`*_>\[\]\(\)\{\}|]", " ", head)

    words = re.findall(r"[a-zæøå]+", head, flags=re.IGNORECASE)
    if len(words) < 60:
        return False

    norwegian = {
        "og",
        "ikke",
        "som",
        "for",
        "med",
        "til",
        "av",
        "på",
        "i",
        "skal",
        "kan",
        "må",
        "det",
        "den",
        "dette",
        "disse",
        "fra",
        "ved",
        "hvis",
        "derfor",
        "krav",
        "tiltak",
        "sikkerhet",
        "ansvar",
        "rutine",
        "prosess",
        "drift",
    }
    english = {
        "the",
        "and",
        "to",
        "of",
        "in",
        "for",
        "with",
        "this",
        "that",
        "you",
        "your",
        "should",
        "must",
        "may",
        "can",
        "will",
        "we",
        "it",
        "is",
        "are",
        "as",
        "be",
        "please",
        "summary",
        "recommendations",
        "proposal",
        "wastewater",
        "treatment",
    }

    n_count = sum(1 for w in words if w in norwegian)
    e_count = sum(1 for w in words if w in english)
    if e_count >= 14 and e_count > (n_count * 1.4) and n_count < 12:
        return True
    return False


def _truncate_for_readable_excerpt(text: str, *, max_chars: int) -> tuple[str, bool]:
    """Truncate long excerpts at natural boundaries to avoid abrupt cut-offs."""

    raw = (text or "").strip()
    if len(raw) <= max_chars:
        return raw, False

    # Keep a little headroom for marker text and formatting.
    hard_limit = max(500, max_chars - 120)
    head = raw[:hard_limit]
    min_accept = int(hard_limit * 0.65)

    cut_candidates = [
        head.rfind("\n\n"),
        head.rfind(".\n"),
        head.rfind("!\n"),
        head.rfind("?\n"),
        head.rfind(". "),
        head.rfind("! "),
        head.rfind("? "),
        head.rfind("\n"),
    ]
    cut = max(cut_candidates)

    # If no good boundary is found near the end, fall back to last space.
    if cut < min_accept:
        cut = head.rfind(" ")
    if cut < max(150, int(hard_limit * 0.5)):
        cut = hard_limit

    excerpt = head[:cut].rstrip()
    excerpt = excerpt.rstrip("-,:; ")
    return excerpt + "\n\n[... utdraget er forkortet ...]", True


def fallback_structured_document_short(original_filename: str, content: str) -> str:
    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    cleaned = clean_extracted_text(content)
    # If we only have a TOC, generate a more helpful deterministic structured draft.
    if _looks_like_table_of_contents(cleaned) and not extract_abstract(cleaned):
        entries = _extract_toc_entries(cleaned)
        if entries and len(entries) >= 8:
            return toc_only_structured_draft(original_filename, cleaned)
    abstract = extract_abstract(cleaned, max_chars=1200)
    snippet = cleaned[:800].strip()
    summary_source = abstract or snippet or "Innhold ikke tilgjengelig."

    body = f"# {title}\n\n## Utdrag\n\n{summary_source}\n"

    return render_markdown_with_frontmatter(title=safe_title, body=body)


def fallback_structured_document_long(original_filename: str, content: str) -> str:
    """Longer deterministic fallback.

    Grounded: includes full cleaned source text so the reviewer does not lose content.
    """

    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    cleaned = clean_extracted_text(content)

    # Do not downsample here: fallback should preserve as much of the source as possible.
    excerpt = cleaned.strip()
    if not excerpt:
        excerpt = (content or "").strip() or "Innhold ikke tilgjengelig."

    body = f"# {title}\n\n## Utdrag (kilde)\n\n{excerpt}\n"

    return render_markdown_with_frontmatter(title=safe_title, body=body)


def unreadable_pdf_message(original_filename: str) -> str:
    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    body = (
        f"# {title}\n\n"
        "## Kort sammendrag\n"
        "- Dokumentet ser ut til å mangle maskinlesbar tekst (typisk skannet PDF/bildebasert).\n"
        "- KI kan derfor ikke lage et revidert sammendrag uten OCR/tekstgrunnlag.\n\n"
        "## Hva du kan gjøre\n"
        "- Last opp en tekstbasert PDF (kopierbar tekst) eller en `.txt`/`.docx`-versjon.\n"
        "- Alternativt: kjør OCR på PDF-en og last opp den OCR’ede filen.\n"
    )

    return render_markdown_with_frontmatter(title=safe_title, body=body)


def build_plan(text: str) -> GenerationPlan:
    words = word_count(text)

    if words <= 900:
        windows = 3
        window_chars = 2600
        max_source_chars = 24000
        num_predict = 2400
    elif words <= 2000:
        windows = 4
        window_chars = 3000
        max_source_chars = 45000
        num_predict = 3600
    elif words <= 5000:
        windows = 5
        window_chars = 3200
        max_source_chars = 65000
        num_predict = 4600
    else:
        windows = 6
        window_chars = 3600
        max_source_chars = 90000
        num_predict = 6400

    # Clamp defensively
    windows = max(2, min(8, windows))
    window_chars = max(1600, min(5200, window_chars))
    max_source_chars = max(12000, min(240000, max_source_chars))
    num_predict = max(1200, min(16384, num_predict))

    return GenerationPlan(
        source_words=words,
        windows=windows,
        window_chars=window_chars,
        max_source_chars=max_source_chars,
        num_predict=num_predict,
    )


def sample_windows(cleaned: str, *, windows: int, window_chars: int) -> list[tuple[str, str]]:
    L = len(cleaned)
    if L <= 0:
        return []

    positions: list[int] = []
    if windows == 2:
        positions = [0, max(0, L - (window_chars + 600))]
    else:
        for i in range(windows):
            frac = i / max(1, windows - 1)
            positions.append(int(L * frac))
        positions[-1] = max(0, L - (window_chars + 900))

    def take(start: int) -> str:
        start = max(0, min(start, max(0, L - 1)))

        # Avoid starting mid-word: back up to whitespace/newline if needed.
        if 0 < start < L and cleaned[start].isalnum() and cleaned[start - 1].isalnum():
            back_limit = max(0, start - 80)
            j = start
            while j > back_limit and cleaned[j - 1] not in {" ", "\n", "\t"}:
                j -= 1
            start = j

        end = min(L, start + window_chars)

        # Avoid ending mid-word: extend to next whitespace/newline if close.
        if 0 < end < L and cleaned[end - 1].isalnum() and cleaned[end].isalnum():
            forward_limit = min(L, end + 120)
            k = end
            while k < forward_limit and cleaned[k] not in {" ", "\n", "\t"}:
                k += 1
            end = k

        # Prefer aligning to line boundaries for readability.
        if start > 0:
            prev_nl = cleaned.rfind("\n", max(0, start - 260), start)
            if prev_nl != -1:
                start = prev_nl + 1
        if end < L:
            next_nl = cleaned.find("\n", end, min(L, end + 320))
            if next_nl != -1:
                end = next_nl

        return cleaned[start:end].strip()

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for idx, pos in enumerate(positions):
        chunk = take(pos)
        if not chunk:
            continue
        key = chunk[:250]
        if key in seen:
            continue
        seen.add(key)
        label = "START" if idx == 0 else ("END" if idx == len(positions) - 1 else f"MID{idx}")
        out.append((label, chunk))

    return out


def format_source_pack(cleaned: str, windows_out: list[tuple[str, str]], *, max_chars: int) -> str:
    abstract = extract_abstract(cleaned)
    conclusion = extract_conclusion(cleaned)

    parts: list[str] = []
    for label, chunk in windows_out:
        parts.append(f"[UTDRAG: {label}]\n{chunk}")
    if abstract:
        parts.append("[UTDRAG: ABSTRACT]\n" + abstract)
    if conclusion:
        parts.append("[UTDRAG: CONCLUSION]\n" + conclusion)

    joined = "\n\n".join(parts).strip() or cleaned[:max_chars].strip()
    return joined[:max_chars].strip()


_STRUCTURED_JSON_PROMPT = """
Du er en agent som skal lage et revidert forslag basert KUN på utdragene.

ABSOLUTT KRAV:
- Ikke dikt opp fakta eller tiltak. Hvis noe ikke står i utdraget: skriv "(ikke oppgitt i utdraget)".
- Ikke bruk generelle best practices eller bransjekunnskap.
- Ikke spør spørsmål.
- Skriv på norsk (bokmål).

VIKTIG FOR Å UNNGÅ HALLUSINASJON:
- HVER bullet (hver streng i listene) MÅ avsluttes med et eksakt sitat fra utdraget som bevis:
    (KILDE: "<eksakt sitat fra utdraget>")
- Sitatet må være en direkte kopi av en tekstbit som finnes i utdraget.
- Hvis du ikke finner passende sitat for en bullet, skriv heller "(ikke oppgitt i utdraget)" som egen bullet (uten KILDE).

MÅL (mer detaljert og gjerne lengre):
- "Kort sammendrag": 6–12 bullets.
- "Viktigste punkter": 10–22 bullets.
- "Kapittelvis sammendrag": 8–25 bullets (bevar kapittel/underkapittel hvis synlig).
- "Relevante detaljer": 6–20 bullets (tall, krav, roller, frekvenser, utstyr, prosedyrer – kun hvis i utdraget).
- "Eventuelle tiltak / anbefalinger": tom liste hvis tiltak ikke eksplisitt står i utdraget.

KVALITETSKRAV (IKKE FOR TYNT):
- Ikke returner kun 1-3 korte punkter totalt.
- Ikke bruk bare seksjonstitler eller nøkkelord som punktinnhold.
- Hvis kilden er rik på innhold, må forslaget også være innholdsrikt og dekke flere hoveddeler.
- Bruk "(ikke oppgitt i utdraget)" bare når informasjon faktisk mangler i kilden.

OUTPUT (STRENGT):
- Returner KUN gyldig JSON. Ingen Markdown, ingen kodegjerder, ingen forklaring.

JSON-SKJEMA:
{
    "title": string,
    "tags": string[],
    "category": "Sikkerhet"|"Vedlikehold"|"Miljø"|"Kvalitet"|"Prosedyre"|"Annet",
    "review_status": "pending",
    "confidence_score": number,
    "sections": {
        "Kort sammendrag": string[],
        "Viktigste punkter": string[],
        "Kapittelvis sammendrag": string[],
        "Relevante detaljer": string[],
        "Eventuelle tiltak / anbefalinger": string[]
    }
}
""".strip()


_JSON_REPAIR_PROMPT = """
Du er et verktøy som kun reparerer JSON.

KRAV:
- Returner KUN gyldig JSON (ingen tekst rundt).
- Ikke legg til nye fakta; bruk "(ikke oppgitt i utdraget)".
- Skriv på norsk (bokmål).
- Følg eksakt samme JSON-skjema som oppgitt.
""".strip()


def _extract_json(text: str) -> str | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    m = _JSON_OBJECT_RE.search(t)
    if not m:
        return None
    return (m.group(0) or "").strip()


def _normalize_json_payload(payload: dict, *, original_filename: str) -> dict:
    title = str(payload.get("title") or Path(original_filename).stem or "Untitled").strip()
    if not title:
        title = Path(original_filename).stem or "Untitled"

    tags = payload.get("tags")
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []
    tags_out = [str(t).strip() for t in tags if str(t).strip()][:24]

    category = payload.get("category")
    if not isinstance(category, str) or category not in _ALLOWED_CATEGORIES:
        category = "Annet"

    review_status = "pending"

    confidence = payload.get("confidence_score")
    try:
        confidence_f = float(confidence)
    except Exception:
        confidence_f = 0.6
    confidence_f = max(0.0, min(1.0, confidence_f))

    sections = payload.get("sections")
    if not isinstance(sections, dict):
        sections = {}

    def normalize_section_item(x) -> list[str]:
        if isinstance(x, dict):
            title_part = str(x.get("title") or "").strip()
            content_raw = x.get("content")

            content_items: list[str] = []
            if isinstance(content_raw, str):
                s = content_raw.strip()
                if s:
                    content_items = [s]
            elif isinstance(content_raw, list):
                content_items = [str(c).strip() for c in content_raw if str(c).strip()]

            out: list[str] = []
            if content_items:
                for c in content_items:
                    if title_part and c != "(ikke oppgitt i utdraget)":
                        out.append(f"{title_part}: {c}")
                    else:
                        out.append(c)
                return out

            if title_part:
                return [title_part]
            return []

        s = str(x or "").strip()
        return [s] if s else []

    def get_list(name: str) -> list[str]:
        v = sections.get(name)
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v:
            out.extend(normalize_section_item(x))
        return out

    normalized_sections = {
        "Kort sammendrag": get_list("Kort sammendrag"),
        "Viktigste punkter": get_list("Viktigste punkter"),
        "Kapittelvis sammendrag": get_list("Kapittelvis sammendrag"),
        "Relevante detaljer": get_list("Relevante detaljer"),
        "Eventuelle tiltak / anbefalinger": get_list("Eventuelle tiltak / anbefalinger"),
    }

    return {
        "title": title,
        "tags": tags_out,
        "category": category,
        "review_status": review_status,
        "confidence_score": confidence_f,
        "sections": normalized_sections,
    }


def _validate_payload(payload: dict) -> str | None:
    for key in ("title", "tags", "category", "review_status", "confidence_score", "sections"):
        if key not in payload:
            return f"missing:{key}"

    if not isinstance(payload["title"], str) or not payload["title"].strip():
        return "invalid:title"
    if not isinstance(payload["tags"], list) or any((not isinstance(t, str)) for t in payload["tags"]):
        return "invalid:tags"
    if payload["category"] not in _ALLOWED_CATEGORIES:
        return "invalid:category"
    if payload["review_status"] != "pending":
        return "invalid:review_status"
    try:
        c = float(payload["confidence_score"])
    except Exception:
        return "invalid:confidence_score"
    if c < 0.0 or c > 1.0:
        return "invalid:confidence_score"
    if not isinstance(payload["sections"], dict):
        return "invalid:sections"

    # Must have at least the two core sections.
    if not payload["sections"].get("Kort sammendrag"):
        return "missing:section:Kort sammendrag"
    if not payload["sections"].get("Viktigste punkter"):
        return "missing:section:Viktigste punkter"

    return None


def _payload_is_too_thin(payload: dict) -> bool:
    sections = payload.get("sections") or {}
    if not isinstance(sections, dict):
        return True

    def informative_count(name: str) -> int:
        items = sections.get(name) or []
        if not isinstance(items, list):
            return 0
        n = 0
        for x in items:
            s = str(x or "").strip()
            if not s:
                continue
            if s == "(ikke oppgitt i utdraget)":
                continue
            if len(s) < 18:
                continue
            n += 1
        return n

    kort = informative_count("Kort sammendrag")
    viktigste = informative_count("Viktigste punkter")
    kapittel = informative_count("Kapittelvis sammendrag")
    detaljer = informative_count("Relevante detaljer")

    total = kort + viktigste + kapittel + detaljer

    if kort < 4:
        return True
    if viktigste < 7:
        return True
    if total < 15:
        return True
    return False


def _validate_evidence(payload: dict, *, source_pack: str) -> str | None:
    """Reject bullets that don't provide an exact evidence quote (unless it's the explicit missing marker)."""

    src = source_pack or ""
    src_norm = _normalize_for_evidence_match(src)
    sections = payload.get("sections") or {}
    if not isinstance(sections, dict):
        return "invalid:evidence:sections"

    for section_name, items in sections.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, str):
                return f"invalid:evidence:item_type:{section_name}"
            s = item.strip()
            if not s:
                continue
            if s == "(ikke oppgitt i utdraget)":
                continue
            m = _EVIDENCE_RE.search(s)
            if not m:
                return f"missing:evidence:{section_name}"
            quote = (m.group(1) or "").strip()
            if not quote:
                return f"invalid:evidence:empty_quote:{section_name}"
            quote_norm = _normalize_for_evidence_match(quote)
            if quote_norm and quote_norm in src_norm:
                continue
            if quote not in src:
                return f"invalid:evidence:quote_not_in_source:{section_name}"

    return None


def _collect_source_lines_for_expansion(source_text: str, *, max_items: int = 220) -> list[str]:
    raw = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    seen: set[str] = set()

    verb_signal = re.compile(
        r"\b(skal|må|bor|bør|kan|ansvar|kontroll|vedlikehold|utslipp|tiltak|"
        r"vurderes|reduseres|sendes|holdes|sjekk|stopp|start)\b",
        flags=re.IGNORECASE,
    )

    for ln in raw.split("\n"):
        s = re.sub(r"\s+", " ", (ln or "").strip())
        if not s:
            continue
        if _is_toc_line(s):
            continue
        if re.fullmatch(r"\d+(?:[./]\d+)*", s):
            continue
        s_no_page = re.sub(r"\s+[0-9]{1,4}\s*$", "", s).strip()
        s_no_page = re.sub(r"\s+[ivxlcdm]{1,6}\s*$", "", s_no_page, flags=re.IGNORECASE).strip()
        if not s_no_page:
            continue
        # Exclude chapter-like headings such as "2.1 Utslippskrav ..." without sentence content.
        if re.match(r"^\d+(?:\.\d+)*\s+\S+(?:\s+\S+){0,10}$", s_no_page):
            continue
        if len(s_no_page) < 32:
            continue
        if s_no_page == "(ikke oppgitt i utdraget)":
            continue
        # Prefer lines that look like content sentences, not index labels.
        words = re.findall(r"\b\w+\b", s_no_page, flags=re.UNICODE)
        has_sentence_punct = bool(re.search(r"[,;:]", s_no_page))
        if len(words) < 7 and not has_sentence_punct and not verb_signal.search(s_no_page):
            continue

        key = s_no_page.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s_no_page)
        if len(out) >= max_items:
            break

    return out


def _expand_payload_from_source(payload: dict, *, source_text: str) -> dict:
    """Deterministically expand sparse sections using grounded source lines."""

    p = dict(payload or {})
    sections = p.get("sections")
    if not isinstance(sections, dict):
        sections = {}

    def as_list(name: str) -> list[str]:
        items = sections.get(name)
        if isinstance(items, list):
            return [str(x).strip() for x in items if str(x).strip()]
        if isinstance(items, str):
            s = items.strip()
            return [s] if s else []
        return []

    def is_informative(s: str) -> bool:
        t = (s or "").strip()
        return bool(t) and t != "(ikke oppgitt i utdraget)" and len(t) >= 18

    source_lines = _collect_source_lines_for_expansion(source_text)
    if not source_lines:
        p["sections"] = sections
        return p

    cursor = 0

    def add_until(name: str, *, target_informative: int, max_total: int) -> None:
        nonlocal cursor
        items = as_list(name)
        informative = sum(1 for x in items if is_informative(x))

        existing_keys = {re.sub(r"\s+", " ", x).strip().casefold() for x in items}
        while informative < target_informative and len(items) < max_total and cursor < len(source_lines):
            line = source_lines[cursor]
            cursor += 1
            key = line.casefold()
            if key in existing_keys:
                continue

            quote = line[:200].strip().replace('"', "'")
            bullet = f"{line} (KILDE: \"{quote}\")"
            items.append(bullet)
            existing_keys.add(key)
            informative += 1

        sections[name] = items

    # Keep quotas modest to avoid overloading the reviewer, but high enough to avoid thin output.
    add_until("Kort sammendrag", target_informative=6, max_total=12)
    add_until("Viktigste punkter", target_informative=9, max_total=16)
    add_until("Kapittelvis sammendrag", target_informative=6, max_total=20)
    add_until("Relevante detaljer", target_informative=5, max_total=14)

    p["sections"] = sections
    return p


def render_yaml_markdown(payload: dict) -> str:
    title = payload["title"]
    front = {
        "title": title,
        "tags": payload.get("tags", []),
        "category": payload.get("category", "Annet"),
        "review_status": "pending",
        "confidence_score": float(payload.get("confidence_score", 0.6)),
    }

    sections: dict = payload.get("sections") or {}

    def bullets(items: list[str]) -> str:
        if not items:
            return "- (ikke oppgitt i utdraget)"
        return "\n".join([f"- {x}" for x in items])

    order = [
        _SECTION_SHORT,
        _SECTION_KEY,
        _SECTION_CHAPTER,
        _SECTION_DETAILS,
        _SECTION_ACTIONS,
    ]

    body_parts = [f"# {title}"]
    for name in order:
        items = sections.get(name) or []
        body_parts.append(f"## {name}\n{bullets(items)}")

    yaml_block = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip() + "\n---\n\n"
    return yaml_block + "\n\n".join(body_parts).strip() + "\n"


def _build_enrichment_input(*, source_pack: str, payload: dict, last_problem: str | None) -> str:
    return (
        "KILDEUTDRAG (kun fakta herfra):\n\n"
        + source_pack[:14000]
        + "\n\n"
        + "OPPGAVE: JSON-utkastet under er for tynt. Utvid det med flere konkrete og informative punkter, "
        + "uten å finne på noe.\n"
        + "KRAV:\n"
        + "- Hold deg til fakta i kildeteksten.\n"
        + "- Behold eksisterende struktur og felter.\n"
        + "- Legg til substans i 'Kort sammendrag', 'Viktigste punkter', 'Kapittelvis sammendrag' og 'Relevante detaljer'.\n"
        + "- Ikke bruk generiske fyllpunkter.\n"
        + "- Returner KUN gyldig JSON i samme skjema.\n\n"
        + (f"SISTE PROBLEM: {last_problem}\n\n" if last_problem else "")
        + "NÅVÆRENDE JSON (forbedre denne):\n\n"
        + json.dumps(payload, ensure_ascii=False)[:12000]
    )


def _build_seeded_rewrite_input(
    *,
    source_pack: str,
    seeded_markdown: str,
    payload: dict,
    last_problem: str | None,
) -> str:
    return (
        "KILDEUTDRAG (kun fakta herfra):\n\n"
        + source_pack[:18000]
        + "\n\n"
        + "UTKAST-MAL (deterministisk fallback, bruk som strukturhjelp - ikke som ny faktakilde):\n\n"
        + seeded_markdown[:18000]
        + "\n\n"
        + "OPPGAVE: Lag et fyldigere JSON-utkast fra kildeteksten. "
        + "Bruk malen for struktur og dekning, men all fakta ma komme fra kildeteksten.\n"
        + "KRAV:\n"
        + "- Hold deg 100% til fakta i kildeteksten.\n"
        + "- Returner KUN gyldig JSON i samme skjema.\n"
        + "- Fyll ut med flere informative punkter i hovedseksjonene.\n"
        + "- Ikke bruk generiske fyllpunkter.\n"
        + "- Hvis informasjon mangler, bruk '(ikke oppgitt i utdraget)'.\n"
        + "- Behold eksisterende metadata-felter.\n\n"
        + (f"SISTE PROBLEM: {last_problem}\n\n" if last_problem else "")
        + "NÅVÆRENDE JSON (kan forbedres):\n\n"
        + json.dumps(payload, ensure_ascii=False)[:12000]
    )


def generate_revised_suggestion(
    *,
    agent,
    original_filename: str,
    extracted_text: str,
    llm_options: dict,
) -> tuple[str, dict]:
    """Generate a revised suggestion.

    Returns: (suggestion_text, diagnostics)
    diagnostics: {fallback_used:int, reason:str|None, error:str|None}
    """

    cleaned = clean_extracted_text(extracted_text)
    if is_effectively_empty(cleaned):
        # Caller should normally skip background generation in this case, but be safe.
        return (
            unreadable_pdf_message(original_filename),
            {"fallback_used": 1, "reason": "no_extractable_text", "error": None},
        )

    # If the extracted text is essentially only a table of contents, don't call the LLM.
    if _looks_like_table_of_contents(cleaned):
        entries = _extract_toc_entries(cleaned)
        if entries and len(entries) >= 8:
            return (
                toc_only_structured_draft(original_filename, cleaned),
                {"fallback_used": 1, "reason": "toc_only", "error": None},
            )

    plan = build_plan(cleaned)

    # Prefer full cleaned source when it fits budget to avoid overly narrow summaries.
    if len(cleaned) <= plan.max_source_chars:
        source_pack = cleaned
    else:
        windows_out = sample_windows(cleaned, windows=plan.windows, window_chars=plan.window_chars)
        source_pack = format_source_pack(cleaned, windows_out, max_chars=plan.max_source_chars)

    payload: dict | None = None
    last_problem: str | None = None
    raw = agent.process_document(
        _STRUCTURED_JSON_PROMPT,
        source_pack,
        max_input_chars=plan.max_source_chars,
        llm_options={"format": "json", "temperature": 0, "num_predict": plan.num_predict, **(llm_options or {})},
    )

    for _attempt in range(2):
        json_text = _extract_json(raw or "")
        if json_text:
            try:
                parsed = json.loads(json_text)
                if isinstance(parsed, dict):
                    payload = _normalize_json_payload(parsed, original_filename=original_filename)
                    err = _validate_payload(payload)
                    if err is None:
                        ev = _validate_evidence(payload, source_pack=source_pack)
                        if ev is None:
                            break
                        # Keep the structured draft even if evidence markers are weak.
                        # This avoids unnecessary fallback for long/noisy documents.
                        last_problem = f"weak_evidence:{ev}"
                        break
                    last_problem = f"validate:{err}"
                    payload = None
            except Exception:
                last_problem = "json_parse_error"
                payload = None

        # Repair attempt
        repair_input = (
            "KILDEUTDRAG (kun fakta herfra):\n\n"
            + source_pack[:10000]
            + "\n\nKRAV: Returner KUN gyldig JSON (ingen tekst rundt).\n"
            + "Bruk '(ikke oppgitt i utdraget)' der informasjon mangler.\n"
            + "GYLDIG KATEGORI: Sikkerhet|Vedlikehold|Miljø|Kvalitet|Prosedyre|Annet\n"
            + "review_status MÅ være 'pending'.\n\n"
            + "JSON-SKJEMA (må følges):\n"
            + "{\n"
            + "  \"title\": string,\n"
            + "  \"tags\": string[],\n"
            + "  \"category\": \"Sikkerhet\"|\"Vedlikehold\"|\"Miljø\"|\"Kvalitet\"|\"Prosedyre\"|\"Annet\",\n"
            + "  \"review_status\": \"pending\",\n"
            + "  \"confidence_score\": number,\n"
            + "  \"sections\": {\n"
            + "    \"Kort sammendrag\": string[],\n"
            + "    \"Viktigste punkter\": string[],\n"
            + "    \"Kapittelvis sammendrag\": string[],\n"
            + "    \"Relevante detaljer\": string[],\n"
            + "    \"Eventuelle tiltak / anbefalinger\": string[]\n"
            + "  }\n"
            + "}\n\n"
            + (f"SISTE PROBLEM: {last_problem}\n\n" if last_problem else "")
            + "Ugyldig output som må repareres til gyldig JSON:\n\n"
            + (raw or "")[:8000]
        )
        raw = agent.process_document(
            _JSON_REPAIR_PROMPT,
            repair_input,
            max_input_chars=min(plan.max_source_chars, 20000),
            llm_options={"format": "json", "temperature": 0, "num_predict": min(2400, plan.num_predict), **(llm_options or {})},
        )

    if payload is None:
        # One last direct retry with larger budget before we fall back.
        retry_num_predict = min(16384, max(plan.num_predict + 1200, int(plan.num_predict * 1.35)))
        retry_max_input = min(240000, max(plan.max_source_chars, int(plan.max_source_chars * 1.25)))
        retry_source = cleaned[:retry_max_input]

        try:
            raw_retry = agent.process_document(
                _STRUCTURED_JSON_PROMPT,
                retry_source,
                max_input_chars=retry_max_input,
                llm_options={"format": "json", "temperature": 0, "num_predict": retry_num_predict, **(llm_options or {})},
            )

            json_retry = _extract_json(raw_retry or "")
            if json_retry:
                parsed_retry = json.loads(json_retry)
                if isinstance(parsed_retry, dict):
                    payload_retry = _normalize_json_payload(parsed_retry, original_filename=original_filename)
                    err_retry = _validate_payload(payload_retry)
                    if err_retry is None:
                        ev_retry = _validate_evidence(payload_retry, source_pack=retry_source)
                        if ev_retry is None:
                            payload = payload_retry
                        else:
                            last_problem = f"retry:evidence:{ev_retry}"
                    else:
                        last_problem = f"retry:validate:{err_retry}"
            else:
                last_problem = last_problem or "retry:no_json"
        except Exception:
            last_problem = last_problem or "retry:exception"

    if payload is None:
        return (
            fallback_structured_document_long(original_filename, cleaned),
            {"fallback_used": 1, "reason": "json_invalid_after_retry", "error": last_problem},
        )

    if _payload_is_too_thin(payload):
        try:
            enrich_input = _build_enrichment_input(source_pack=source_pack, payload=payload, last_problem=last_problem)
            raw_enrich = agent.process_document(
                _JSON_REPAIR_PROMPT,
                enrich_input,
                max_input_chars=min(240000, max(plan.max_source_chars, 24000)),
                llm_options={
                    "format": "json",
                    "temperature": 0,
                    "num_predict": min(5200, max(plan.num_predict, 3200)),
                    **(llm_options or {}),
                },
            )

            json_enrich = _extract_json(raw_enrich or "")
            if json_enrich:
                parsed_enrich = json.loads(json_enrich)
                if isinstance(parsed_enrich, dict):
                    payload_enrich = _normalize_json_payload(parsed_enrich, original_filename=original_filename)
                    err_enrich = _validate_payload(payload_enrich)
                    if err_enrich is None and not _payload_is_too_thin(payload_enrich):
                        payload = payload_enrich
                    else:
                        last_problem = f"enrich:{err_enrich or 'still_thin'}"
        except Exception:
            last_problem = last_problem or "enrich:exception"

    if _payload_is_too_thin(payload):
        try:
            seeded_markdown = fallback_structured_document_long(original_filename, cleaned)
            seeded_input = _build_seeded_rewrite_input(
                source_pack=source_pack,
                seeded_markdown=seeded_markdown,
                payload=payload,
                last_problem=last_problem,
            )
            raw_seeded = agent.process_document(
                _JSON_REPAIR_PROMPT,
                seeded_input,
                max_input_chars=min(240000, max(plan.max_source_chars, 28000)),
                llm_options={
                    "format": "json",
                    "temperature": 0,
                    "num_predict": min(6200, max(plan.num_predict, 3600)),
                    **(llm_options or {}),
                },
            )

            json_seeded = _extract_json(raw_seeded or "")
            if json_seeded:
                parsed_seeded = json.loads(json_seeded)
                if isinstance(parsed_seeded, dict):
                    payload_seeded = _normalize_json_payload(parsed_seeded, original_filename=original_filename)
                    err_seeded = _validate_payload(payload_seeded)
                    if err_seeded is None and not _payload_is_too_thin(payload_seeded):
                        payload = payload_seeded
                    else:
                        last_problem = f"seeded:{err_seeded or 'still_thin'}"
        except Exception:
            last_problem = last_problem or "seeded:exception"

    if _payload_is_too_thin(payload):
        payload = _expand_payload_from_source(payload, source_text=cleaned)
        if _payload_is_too_thin(payload):
            last_problem = last_problem or "deterministic_expand:still_thin"
        else:
            last_problem = None

    payload = _postprocess_payload_sections(
        payload,
        evidence_re=_EVIDENCE_RE,
        is_toc_line=_is_toc_line,
        missing_marker=_MISSING_MARKER,
    )

    thin_output = _payload_is_too_thin(payload)
    if thin_output and not last_problem:
        last_problem = "thin_output"

    rendered = render_yaml_markdown(payload)
    if looks_like_non_norwegian(rendered):
        # One more attempt: translate/repair to Norwegian while keeping evidence quotes intact.
        translate_prompt = (
            "Du skal oversette/forbedre følgende JSON til norsk (bokmål) uten å endre fakta.\n"
            "KRAV: Behold alle (KILDE: \"...\") sitater uendret.\n"
            "Returner KUN gyldig JSON i samme skjema.\n\n"
            + (json.dumps(payload, ensure_ascii=False)[:12000])
        )
        raw2 = agent.process_document(
            _JSON_REPAIR_PROMPT,
            translate_prompt,
            max_input_chars=14000,
            llm_options={"format": "json", "temperature": 0, "num_predict": min(2200, plan.num_predict), **(llm_options or {})},
        )
        json2 = _extract_json(raw2 or "")
        if json2:
            try:
                parsed2 = json.loads(json2)
                if isinstance(parsed2, dict):
                    payload2 = _normalize_json_payload(parsed2, original_filename=original_filename)
                    payload2 = _postprocess_payload_sections(
                        payload2,
                        evidence_re=_EVIDENCE_RE,
                        is_toc_line=_is_toc_line,
                        missing_marker=_MISSING_MARKER,
                    )
                    err2 = _validate_payload(payload2)
                    if err2 is None and not looks_like_non_norwegian(render_yaml_markdown(payload2)):
                        ev2 = _validate_evidence(payload2, source_pack=source_pack)
                        if ev2 is not None:
                            last_problem = f"weak_evidence:{ev2}"
                        payload = payload2
                        rendered = render_yaml_markdown(payload2)
            except Exception:
                pass

    if looks_like_non_norwegian(rendered):
        # Last resort: don't ship English. Provide grounded Norwegian deterministic draft.
        return (
            fallback_structured_document_long(original_filename, cleaned),
            {"fallback_used": 1, "reason": "non_norwegian", "error": "language_check_failed"},
        )

    return (
        rendered,
        {
            "fallback_used": 0,
            "reason": "thin_output" if thin_output else None,
            "error": last_problem if thin_output else None,
        },
    )
