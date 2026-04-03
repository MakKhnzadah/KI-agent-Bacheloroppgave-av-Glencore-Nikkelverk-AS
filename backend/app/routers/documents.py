from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.document_processing.document_parsing import parse_document
from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT
from app.workflow_db.config import get_repo_root
from app.workflow_db.db import get_connection

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
_PROCESSING_MODEL_MARKER = "__processing__"
# Upload-time structuring defaults. These are intentionally conservative; budgets are adapted per-document.
_STRUCTURING_NUM_PREDICT_DEFAULT = 2600
_STRUCTURING_NUM_PREDICT_MAX = 12288
_STRUCTURING_SOURCE_MAX_CHARS_DEFAULT = 60000
_STRUCTURING_SOURCE_MAX_CHARS_MAX = 240000
_MIN_EXTRACTED_WORDS = 40

# Multi-pass structuring: first summarize windows, then write the final draft.
_STRUCTURING_MULTIPASS_ENABLED = os.getenv("STRUCTURING_MULTIPASS", "1").strip().lower() not in {"0", "false", "no"}
_STRUCTURING_MULTIPASS_MIN_WORDS = int(os.getenv("STRUCTURING_MULTIPASS_MIN_WORDS", "10000"))
_STRUCTURING_MULTIPASS_MAX_WINDOWS = int(os.getenv("STRUCTURING_MULTIPASS_MAX_WINDOWS", "10"))

_WINDOW_SUMMARY_PROMPT = """
Du skal oppsummere et UTDRAG fra et lengre dokument.

REGLER:
- Ikke dikt opp nye fakta. Hvis noe mangler, skriv "(ikke oppgitt i utdraget)".
- Skriv kort og konkret.
- Bruk Markdown med overskrift og punktlister.
- Ikke still spørsmål eller be om avklaringer.

FORMAT:
## <LABEL>
- Tema: ...
- Viktige punkter: ... (3–8 bullets)
- Begreper/teknologi: ... (0–5 bullets)
- Tiltak/anbefalinger: ... (0–5 bullets)

EKSTRA KRAV FOR KVALITET:
- Ikke lag rene keyword-lister uten forklaring.
- Hver bullet skal være forklarende (hel setning eller informativt fragment), ikke bare 1–3 ord.
"""

_STRUCTURING_REPAIR_PROMPT = """
Du er en agent som kun REFORMATERER og KONDENSERER tekst til et godkjenningsklart Markdown-dokument.

Du vil få en linje `TARGET_WORDS: <min>-<max>`. Hold deg innenfor dette spenn (ca.).

STRENGT OUTPUT-FORMAT (må følges nøyaktig):
1. Output MÅ starte med:
---
2. YAML-delen MÅ inneholde:
    - title
    - tags (liste)
    - category (én av: Sikkerhet, Vedlikehold, Miljø, Kvalitet, Prosedyre, Annet)
    - review_status (sett til "pending")
    - confidence_score (0.0 - 1.0)
3. YAML MÅ avsluttes med:
---
4. Etter YAML skal du skrive Markdown-innholdet.

KRAV:
- Body må starte med `# <title>`.
- Body må ha minst én `##`-seksjon.
- Følg `TARGET_WORDS` (kort men informativt).
- Del opp med overskrifter for pusterom.
- Unngå "outline-only" output: Ikke list kun overskrifter eller nøkkelord uten forklaring.
- Hver bullet skal være informativ (hel setning eller forklarende fragment), ikke enkeltord.
- Ikke still spørsmål eller be om avklaringer.
- Inkluder minst disse seksjonene (hvis mulig gitt kilden):
    - `## Kort sammendrag` (3–8 punkt)
    - `## Viktigste punkter` (5–12 punkt)
    - `## Kapittelvis sammendrag` (4–10 korte underpunkter, bevar nummerering hvis den finnes)
    - `## Relevante detaljer` (tall/krav/roller/datoer)
    - `## Eventuelle tiltak / anbefalinger` (hvis kilden antyder tiltak)
- Ikke legg til tekst før/etter dokumentet.
- Ikke bruk kodeblokker.
"""

llm_provider = OllamaProvider()
agent = AgentService(llm_provider)


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_ALLOWED_CATEGORIES = {"Sikkerhet", "Vedlikehold", "Miljø", "Kvalitet", "Prosedyre", "Annet"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sanitize_filename(name: str) -> str:
    name = Path(name).name  # drop any paths
    name = name.strip().replace(" ", "_")
    name = _FILENAME_SAFE_RE.sub("_", name)
    if not name:
        return "upload"
    return name[:180]


def _fallback_structured_document(original_filename: str, content: str) -> str:
    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    body = (content or "").strip() or "Innhold ikke tilgjengelig."
    return (
        "---\n"
        f"title: \"{safe_title}\"\n"
        "tags: []\n"
        "category: \"Annet\"\n"
        "review_status: \"pending\"\n"
        "confidence_score: 0.0\n"
        "---\n\n"
        f"{body}\n"
    )


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _looks_like_low_information_outline(markdown_body: str) -> bool:
    """Detect drafts that are mostly headings/keywords (low KB value).

    We want bullets/sentences that carry meaning, not just a table-of-contents style list.
    This is heuristic by design.
    """

    body = (markdown_body or "").strip()
    if not body:
        return False

    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if len(lines) < 12:
        return False

    heading_lines = [ln for ln in lines if ln.startswith("#")]
    non_heading = [ln for ln in lines if not ln.startswith("#")]
    if not non_heading:
        return True

    def is_keywordy(ln: str) -> bool:
        # keyword-like line: very short, no punctuation, no digits, not a real sentence.
        if ln.startswith(("- ", "* ")):
            ln = ln[2:].strip()
        words = re.findall(r"\b\w+\b", ln)
        if len(words) <= 3:
            if re.search(r"[\.:;,_\(\)\[\]/]", ln):
                return False
            if re.search(r"\d", ln):
                return False
            # avoid classifying normal short confirmations as keyword lists
            return True
        return False

    keywordy = sum(1 for ln in non_heading if is_keywordy(ln))
    keywordy_ratio = keywordy / max(1, len(non_heading))

    # If most content lines are just keywords, it's effectively an outline.
    if keywordy >= 8 and keywordy_ratio >= 0.30:
        return True

    # Too many headings with too little explanatory text.
    if len(heading_lines) >= 6 and len(non_heading) <= 10:
        return True

    # If very few lines contain sentence-like punctuation, likely an outline.
    punct = sum(1 for ln in non_heading if re.search(r"[\.!?:]", ln))
    if punct <= max(2, int(len(non_heading) * 0.12)) and keywordy >= 6:
        return True

    return False


def _looks_like_chatty_assistant(markdown_body: str) -> bool:
    """Detect responses that look like a general chat assistant asking for clarification.

    Upload-time structuring should never ask the user questions.
    """

    body = (markdown_body or "").strip()
    if not body:
        return False

    head = body[:2500].lower()
    # Common LLM meta-openers.
    bad_phrases = [
        "it looks like you've",
        "it looks like you have",
        "to help me",
        "could you please clarify",
        "let me know if you'd like",
        "what would you like me",
        "do you need help",
        "would you like me to",
        "please clarify",
    ]
    if any(p in head for p in bad_phrases):
        return True

    # Too many question marks early is a red flag.
    if head.count("?") >= 2:
        return True

    # Bullet list of questions.
    lines = [ln.strip() for ln in head.splitlines() if ln.strip()]
    q_bullets = 0
    for ln in lines[:80]:
        if ln.startswith(("- ", "* ")) and "?" in ln:
            q_bullets += 1
    if q_bullets >= 1 and head.count("?") >= 1:
        return True

    return False


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _structuring_plan(text: str) -> dict:
    """Choose a stable input/output budget based on source length.

    Goal: approval-ready drafts that are informative but not a full copy.
    """

    source_words = _word_count(text)

    # Output targets (words) by rough document size.
    if source_words <= 2000:
        target_min, target_max = 700, 1200
        windows = 4
    elif source_words <= 5000:
        target_min, target_max = 1000, 1700
        windows = 5
    elif source_words <= 12000:
        target_min, target_max = 1400, 2300
        windows = 6
    else:
        target_min, target_max = 1800, 2600
        windows = 7

    # Allow smaller drafts for truly short documents.
    if source_words <= 900:
        target_min, target_max = 350, 800
        windows = 3

    # Convert word targets to an approximate token budget.
    # A practical heuristic is ~1.6 tokens per word for English/Norwegian mixed content.
    num_predict = int(target_max * 1.6)
    num_predict = _clamp_int(num_predict, 900, _STRUCTURING_NUM_PREDICT_MAX)
    if source_words > 10000:
        num_predict = max(num_predict, _STRUCTURING_NUM_PREDICT_DEFAULT)

    # Input budget: give enough coverage without blowing up context.
    # Roughly ~7-9 chars per word in normal prose incl. spaces.
    source_max_chars = int(source_words * 8)
    source_max_chars = _clamp_int(
        source_max_chars,
        20000,
        _STRUCTURING_SOURCE_MAX_CHARS_MAX,
    )
    source_max_chars = max(source_max_chars, _STRUCTURING_SOURCE_MAX_CHARS_DEFAULT)

    # Sampling window size: sized so windows + abstract/conclusion fit under max chars.
    window_chars = int(source_max_chars / max(6, (windows + 3)))
    window_chars = _clamp_int(window_chars, 2200, 5200)

    retry_source_max_chars = _clamp_int(int(source_max_chars * 0.7), 14000, source_max_chars)
    retry_num_predict = _clamp_int(int(num_predict * 0.75), 900, _STRUCTURING_NUM_PREDICT_MAX)

    return {
        "source_words": source_words,
        "target_min_words": target_min,
        "target_max_words": target_max,
        "windows": windows,
        "window_chars": window_chars,
        "source_max_chars": source_max_chars,
        "retry_source_max_chars": retry_source_max_chars,
        "num_predict": num_predict,
        "retry_num_predict": retry_num_predict,
    }


def _is_effectively_empty(text: str) -> bool:
    return _word_count(text) < _MIN_EXTRACTED_WORDS


def _strip_pdf_noise_lines(text: str) -> str:
    lines: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue

        # Common IEEE/PDF/Xplore noise
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


def _extract_abstract(text: str, max_chars: int = 2500) -> str | None:
    t = text or ""
    # Match variants like "Abstract—" or "Abstract -"
    m = re.search(r"\bAbstract\s*[—\-:]\s*(.+)", t, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    after = m.group(1)
    # Stop at common section boundary
    stop = re.search(r"\n\s*(Index Terms|I\.|1\.|Introduction)\b", after, flags=re.IGNORECASE)
    abstract = after[: stop.start()] if stop else after
    abstract = abstract.strip()
    if not abstract:
        return None
    return abstract[:max_chars].strip()


def _extract_conclusion(text: str, max_chars: int = 2000) -> str | None:
    t = text or ""
    m = re.search(r"\n\s*(VI\.|V?I?\.?\s*)?CONCLUSION\b\s*\n", t, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\n\s*Conclusion\b\s*\n", t, flags=re.IGNORECASE)
    if not m:
        return None

    tail = t[m.end() :]
    # Stop at references
    stop = re.search(r"\n\s*REFERENCES\b", tail, flags=re.IGNORECASE)
    conclusion = tail[: stop.start()] if stop else tail
    conclusion = conclusion.strip()
    if not conclusion:
        return None
    return conclusion[:max_chars].strip()


def _extract_structuring_source(
    text: str,
    *,
    max_chars: int,
    windows: int = 5,
    window_chars: int = 2600,
) -> str:
    cleaned = _strip_pdf_noise_lines(text)
    if not cleaned.strip():
        cleaned = (text or "").strip()
    abstract = _extract_abstract(cleaned)
    conclusion = _extract_conclusion(cleaned)

    # Sample multiple windows across the document to preserve more context than just the start.
    L = len(cleaned)
    windows = _clamp_int(windows, 2, 10)
    window_chars = _clamp_int(window_chars, 1200, 8000)

    positions: list[int] = []
    if L > 0:
        if windows == 2:
            positions = [0, max(0, L - (window_chars + 600))]
        else:
            for i in range(windows):
                frac = i / max(1, windows - 1)
                positions.append(int(L * frac))
            # Nudge last window a bit earlier to reduce the chance of landing in references.
            positions[-1] = max(0, L - (window_chars + 900))

    def take(start: int) -> str:
        if L <= 0:
            return ""
        start = max(0, min(start, max(0, L - 1)))
        return cleaned[start : start + window_chars].strip()

    windows_out: list[tuple[str, str]] = []
    seen_chunks: set[str] = set()
    for idx, pos in enumerate(positions):
        chunk = take(pos)
        if not chunk:
            continue
        # Avoid duplicates
        key = chunk[:250]
        if key in seen_chunks:
            continue
        seen_chunks.add(key)
        label = "START" if idx == 0 else ("END" if idx == len(positions) - 1 else f"MID{idx}")
        windows_out.append((label, chunk))

    parts: list[str] = []
    for label, chunk in windows_out:
        parts.append(f"[UTDRAG: {label}]\n" + chunk)
    if abstract:
        parts.append("[UTDRAG: ABSTRACT]\n" + abstract)
    if conclusion:
        parts.append("[UTDRAG: CONCLUSION]\n" + conclusion)

    joined = "\n\n".join(parts).strip() or cleaned[:max_chars].strip()
    return joined[:max_chars].strip()


def _summarize_windows_for_long_doc(
    *,
    suggestion_id: str,
    windows: list[tuple[str, str]],
    num_predict: int,
) -> str:
    """Summarize each sampled window to improve coverage before final drafting."""

    summaries: list[str] = []
    max_windows = _clamp_int(_STRUCTURING_MULTIPASS_MAX_WINDOWS, 2, 8)
    for label, chunk in windows[:max_windows]:
        content = f"LABEL: {label}\n\nUTDRAG:\n{chunk}"
        out = agent.process_document(
            _WINDOW_SUMMARY_PROMPT,
            content,
            max_input_chars=12000,
            llm_options={"num_predict": num_predict, "temperature": 0},
        )
        out = (out or "").strip()
        if out:
            summaries.append(out)

    if not summaries:
        return ""

    joined = "\n\n".join(summaries)
    logger.info("Window summaries suggestion_id=%s windows=%s chars=%s", suggestion_id, len(summaries), len(joined))
    return joined


def _coerce_structured_suggestion(original_filename: str, suggestion: str) -> str:
    """Best-effort: ensure YAML frontmatter + minimal markdown structure.

    This avoids throwing away otherwise good model output just because it missed the wrapper.
    """

    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")

    fields, body = _parse_frontmatter(suggestion)
    if fields is None:
        # No YAML: wrap the entire suggestion as body.
        body = (suggestion or "").strip()
        fields = {
            "title": safe_title,
            "tags": "[]",
            "category": "Annet",
            "review_status": "pending",
            "confidence_score": "0.6",
        }
    else:
        # Ensure required keys exist.
        fields.setdefault("title", safe_title)
        fields.setdefault("tags", "[]")
        fields.setdefault("category", "Annet")
        fields.setdefault("review_status", "pending")
        fields.setdefault("confidence_score", "0.6")

    body = (body or "").strip()

    # Minimal markdown structure: title + at least one section.
    if body and not body.lstrip().startswith("# "):
        body = f"# {fields.get('title', safe_title)}\n\n" + body
    elif not body:
        body = f"# {fields.get('title', safe_title)}\n\n## Kort sammendrag\n- (tomt innhold)\n"

    if "\n## " not in ("\n" + body):
        # If model produced a wall of text, wrap it inside a section without dropping content.
        remainder = body
        if remainder.startswith("# "):
            # Drop the first title line to avoid duplicate headings.
            remainder = "\n".join(remainder.splitlines()[1:]).strip()
        if not remainder:
            remainder = "- (mangler innhold)"
        body = f"# {fields.get('title', safe_title)}\n\n## Kort sammendrag\n\n{remainder}\n"

    yaml_block = (
        "---\n"
        f"title: \"{fields.get('title', safe_title)}\"\n"
        f"tags: {fields.get('tags', '[]')}\n"
        f"category: \"{fields.get('category', 'Annet')}\"\n"
        f"review_status: \"{fields.get('review_status', 'pending')}\"\n"
        f"confidence_score: {fields.get('confidence_score', '0.6')}\n"
        "---\n\n"
    )
    return yaml_block + body.strip() + "\n"


def _fallback_structured_document_short(original_filename: str, content: str) -> str:
    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    cleaned = _strip_pdf_noise_lines(content)
    if not cleaned.strip():
        cleaned = (content or "").strip()
    abstract = _extract_abstract(cleaned, max_chars=1200)
    snippet = cleaned[:800].strip()
    summary_source = abstract or snippet or "Innhold ikke tilgjengelig."

    body = (
        f"# {title}\n\n"
        "## Kort sammendrag\n"
        "- Automatisk fallback: AI klarte ikke å levere gyldig strukturert output.\n"
        "- Under er et kort utdrag fra dokumentet for godkjenning / videre bearbeiding.\n\n"
        "## Utdrag\n\n"
        f"{summary_source}\n"
    )

    return (
        "---\n"
        f"title: \"{safe_title}\"\n"
        "tags: []\n"
        "category: \"Annet\"\n"
        "review_status: \"pending\"\n"
        "confidence_score: 0.0\n"
        "---\n\n"
        + body
    )


def _unreadable_pdf_message(original_filename: str) -> str:
    title = Path(original_filename).stem.strip() or "Untitled"
    safe_title = title.replace('"', "'")
    body = (
        f"# {title}\n\n"
        "## Kort sammendrag\n"
        "- Dokumentet ser ut til å mangle maskinlesbar tekst (typisk skannet PDF/bildebasert).\n"
        "- AI kan derfor ikke lage et revidert sammendrag uten OCR/tekstgrunnlag.\n\n"
        "## Hva du kan gjøre\n"
        "- Last opp en tekstbasert PDF (kopierbar tekst) eller en `.txt`/`.docx`-versjon.\n"
        "- Alternativt: kjør OCR på PDF-en og last opp den OCR’ede filen.\n"
    )

    return (
        "---\n"
        f"title: \"{safe_title}\"\n"
        "tags: []\n"
        "category: \"Annet\"\n"
        "review_status: \"pending\"\n"
        "confidence_score: 0.0\n"
        "---\n\n"
        + body
    )


def _parse_frontmatter(markdown_text: str) -> tuple[dict[str, str], str] | tuple[None, None]:
    match = _FRONTMATTER_RE.match((markdown_text or "").strip())
    if not match:
        return None, None

    yaml_block = match.group(1)
    body = (match.group(2) or "").strip()
    fields: dict[str, str] = {}

    for line in yaml_block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")

    return fields, body


def _validate_structured_suggestion(suggestion: str) -> str | None:
    fields, body = _parse_frontmatter(suggestion)
    if fields is None:
        return "Missing or invalid YAML frontmatter"

    required = {"title", "tags", "category", "review_status", "confidence_score"}
    missing = sorted(required - set(fields.keys()))
    if missing:
        return f"Missing YAML keys: {', '.join(missing)}"

    if fields["review_status"] != "pending":
        return "review_status must be 'pending'"

    if fields["category"] not in _ALLOWED_CATEGORIES:
        return f"Invalid category '{fields['category']}'"

    try:
        confidence = float(fields["confidence_score"])
    except ValueError:
        return "confidence_score must be a number between 0.0 and 1.0"

    if confidence < 0.0 or confidence > 1.0:
        return "confidence_score must be between 0.0 and 1.0"

    if not body:
        return "Structured markdown body is empty"

    # Basic readability/structure expectations: title + sections.
    body_lines = [ln.rstrip() for ln in body.splitlines()]
    first_nonempty = next((ln for ln in body_lines[:15] if ln.strip()), "")
    if not first_nonempty.startswith("# "):
        return "Body must start with a '# <title>' heading"

    if "\n## " not in ("\n" + body):
        return "Body must include at least one '##' section heading"

    return None


def _generate_suggestion_async(suggestion_id: str, original_filename: str, processed_text: str) -> None:
    """Generate structured suggestion in background and update the existing row."""
    try:
        if _is_effectively_empty(processed_text):
            suggestions = _unreadable_pdf_message(original_filename)
        else:
            plan = _structuring_plan(processed_text)

            # Build a cleaned view and explicit windows for multi-pass summarization.
            cleaned = _strip_pdf_noise_lines(processed_text)
            if not cleaned.strip():
                cleaned = processed_text

            # Reuse the same sampling logic by calling _extract_structuring_source once, but also
            # compute the actual windows for multi-pass if enabled.
            source_text = _extract_structuring_source(
                cleaned,
                max_chars=plan["source_max_chars"],
                windows=plan["windows"],
                window_chars=plan["window_chars"],
            )

            # Multi-pass for long docs: summarize windows first, then draft from those summaries.
            if (
                _STRUCTURING_MULTIPASS_ENABLED
                and plan["source_words"] >= _STRUCTURING_MULTIPASS_MIN_WORDS
            ):
                # Extract windows again for per-window summarization.
                # This is intentionally simple and deterministic.
                windows_text = _extract_structuring_source(
                    cleaned,
                    max_chars=plan["source_max_chars"],
                    windows=plan["windows"],
                    window_chars=plan["window_chars"],
                )
                # Recover individual windows from the formatted source_text.
                # We store them as tuples by scanning for the [UTDRAG: LABEL] markers.
                window_tuples: list[tuple[str, str]] = []
                current_label: str | None = None
                current_lines: list[str] = []
                for line in (windows_text or "").splitlines():
                    m = re.match(r"^\[UTDRAG: ([A-Z0-9]+)\]$", line.strip())
                    if m:
                        if current_label and current_lines:
                            window_tuples.append((current_label, "\n".join(current_lines).strip()))
                        current_label = m.group(1)
                        current_lines = []
                        continue
                    if current_label and current_label not in {"ABSTRACT", "CONCLUSION"}:
                        current_lines.append(line)
                if current_label and current_lines:
                    window_tuples.append((current_label, "\n".join(current_lines).strip()))

                window_summaries = _summarize_windows_for_long_doc(
                    suggestion_id=suggestion_id,
                    windows=window_tuples,
                    num_predict=_clamp_int(int(plan["num_predict"] * 0.35), 500, 1200),
                )
                if window_summaries:
                    source_text = (
                        "[DEL-SAMMENDRAG FRA DOKUMENTET]\n" + window_summaries + "\n\n" + source_text
                    )
            logger.info(
                "Structuring plan suggestion_id=%s words=%s src_max_chars=%s windows=%s window_chars=%s num_predict=%s target=%s-%s",
                suggestion_id,
                plan["source_words"],
                plan["source_max_chars"],
                plan["windows"],
                plan["window_chars"],
                plan["num_predict"],
                plan["target_min_words"],
                plan["target_max_words"],
            )
            raw = agent.process_document(
                STRUCTURING_AGENT_PROMPT,
                source_text,
                max_input_chars=plan["source_max_chars"],
                llm_options={"num_predict": plan["num_predict"], "temperature": 0},
            )
            suggestions = _coerce_structured_suggestion(original_filename, raw)

            validation_error = _validate_structured_suggestion(suggestions)
            # Also reject outputs that are obviously too long to be an "approval-ready" summary.
            _fields, body = _parse_frontmatter(suggestions)
            body_words = _word_count(body or "")
            too_long = body_words > (plan["target_max_words"] + 650)
            too_short = plan["source_words"] >= 2500 and body_words < max(450, int(plan["target_min_words"] * 0.45))
            outline_only = _looks_like_low_information_outline(body or "")
            chatty = _looks_like_chatty_assistant(body or "")

            if too_short and not validation_error:
                # One extra attempt: same prompt, slightly higher output budget.
                bump = _clamp_int(int(plan["num_predict"] * 1.25), 900, _STRUCTURING_NUM_PREDICT_MAX)
                raw2 = agent.process_document(
                    STRUCTURING_AGENT_PROMPT,
                    source_text,
                    max_input_chars=plan["source_max_chars"],
                    llm_options={"num_predict": bump, "temperature": 0},
                )
                suggestions2 = _coerce_structured_suggestion(original_filename, raw2)
                err2 = _validate_structured_suggestion(suggestions2)
                _f2, b2 = _parse_frontmatter(suggestions2)
                b2_words = _word_count(b2 or "")
                if not err2 and b2_words > body_words:
                    suggestions = suggestions2
                    validation_error = None
                    body_words = b2_words
                    too_long = body_words > (plan["target_max_words"] + 650)
                    too_short = plan["source_words"] >= 2500 and body_words < max(450, int(plan["target_min_words"] * 0.45))

            logger.info(
                "Structuring output suggestion_id=%s body_words=%s too_short=%s too_long=%s validation=%s",
                suggestion_id,
                body_words,
                too_short,
                too_long,
                validation_error,
            )

            if validation_error or too_long or too_short or outline_only or chatty:
                logger.warning(
                    "Suggestion %s needs repair (validation=%s, too_long=%s, body_words=%s, outline_only=%s, chatty=%s)",
                    suggestion_id,
                    validation_error,
                    too_long,
                    body_words,
                    outline_only,
                    chatty,
                )

                # Repair pass: reformat the model output into strict YAML+Markdown, short and sectioned.
                repair_input = (
                    f"FILENAME: {original_filename}\n\n"
                    f"TARGET_WORDS: {plan['target_min_words']}-{plan['target_max_words']}\n\n"
                    "KILDEUTDRAG:\n"
                    f"{source_text[:12000]}\n\n"
                    "MODEL_OUTPUT_SOM_MÅ_REPARERES:\n"
                    f"{raw[:12000]}\n"
                )
                repaired = agent.process_document(
                    _STRUCTURING_REPAIR_PROMPT,
                    repair_input,
                    max_input_chars=plan["retry_source_max_chars"],
                    llm_options={"num_predict": max(plan["retry_num_predict"], int(plan["target_max_words"] * 1.6)), "temperature": 0},
                )
                repaired = _coerce_structured_suggestion(original_filename, repaired)
                repair_error = _validate_structured_suggestion(repaired)
                _rf, repair_body = _parse_frontmatter(repaired)
                repair_too_long = _word_count(repair_body or "") > (plan["target_max_words"] + 650)
                repair_outline_only = _looks_like_low_information_outline(repair_body or "")
                repair_chatty = _looks_like_chatty_assistant(repair_body or "")

                if not repair_error and not repair_too_long and not repair_outline_only and not repair_chatty:
                    suggestions = repaired
                else:
                    # Last resort: retry from a smaller source window.
                    retry_source = _extract_structuring_source(
                        processed_text,
                        max_chars=plan["retry_source_max_chars"],
                        windows=max(3, plan["windows"] - 1),
                        window_chars=plan["window_chars"],
                    )
                    retry_raw = agent.process_document(
                        STRUCTURING_AGENT_PROMPT,
                        retry_source,
                        max_input_chars=plan["retry_source_max_chars"],
                        llm_options={"num_predict": plan["retry_num_predict"], "temperature": 0},
                    )
                    suggestions_retry = _coerce_structured_suggestion(original_filename, retry_raw)
                    retry_error = _validate_structured_suggestion(suggestions_retry)
                    _rf2, retry_body = _parse_frontmatter(suggestions_retry)
                    retry_too_long = _word_count(retry_body or "") > (plan["target_max_words"] + 650)
                    retry_outline_only = _looks_like_low_information_outline(retry_body or "")
                    retry_chatty = _looks_like_chatty_assistant(retry_body or "")

                    if not retry_error and not retry_too_long and not retry_outline_only and not retry_chatty:
                        suggestions = suggestions_retry
                    else:
                        suggestions = _fallback_structured_document_short(original_filename, processed_text)
    except Exception:
        logger.exception("Background suggestion generation failed for %s", suggestion_id)
        suggestions = _fallback_structured_document_short(original_filename, processed_text)

    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE suggestions
                SET suggestion_json = ?, model = ?
                WHERE suggestion_id = ?
                """,
                (suggestions, llm_provider.model, suggestion_id),
            )
    except Exception:
        logger.exception("Failed to persist background suggestion for %s", suggestion_id)


@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    upload_id = str(uuid.uuid4())
    original_filename = file.filename
    safe_filename = _sanitize_filename(original_filename)
    content_sha256 = _sha256_bytes(content)

    guessed_type, _ = mimetypes.guess_type(original_filename)
    content_type = file.content_type
    if not content_type or content_type == "application/octet-stream":
        content_type = guessed_type or "application/octet-stream"

    repo_root = get_repo_root()
    uploads_root = repo_root / "databases" / "data" / "uploads" / upload_id
    uploads_root.mkdir(parents=True, exist_ok=True)
    stored_path = uploads_root / safe_filename
    stored_path.write_bytes(content)

    try:
        processed_text = parse_document(original_filename, content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    extracted_is_empty = _is_effectively_empty(processed_text)

    normalized_id = str(uuid.uuid4())
    normalized_sha256 = _sha256_text(processed_text)
    suggestion_id = str(uuid.uuid4())
    fallback_suggestion = (
        _unreadable_pdf_message(original_filename)
        if extracted_is_empty
        else _fallback_structured_document_short(original_filename, processed_text)
    )

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO uploads (upload_id, original_filename, content_type, size_bytes, sha256, stored_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    upload_id,
                    original_filename,
                    content_type,
                    len(content),
                    content_sha256,
                    str(stored_path.as_posix()),
                ),
            )
            conn.execute(
                """
                INSERT INTO normalized_documents (normalized_id, upload_id, text, sha256)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_id, upload_id, processed_text, normalized_sha256),
            )
            conn.execute(
                """
                INSERT INTO suggestions (suggestion_id, upload_id, suggestion_json, model, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (suggestion_id, upload_id, fallback_suggestion, _PROCESSING_MODEL_MARKER, "draft"),
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist workflow data: {exc}")

    # Perform expensive AI structuring after returning the upload response.
    # If the document has no extractable text, skip the LLM call and keep the message.
    if not extracted_is_empty:
        background_tasks.add_task(_generate_suggestion_async, suggestion_id, original_filename, processed_text)

    return {
        "upload_id": upload_id,
        "suggestion_id": suggestion_id,
        "structured_draft": fallback_suggestion,
        "suggestion_addon": "",
        "suggestions": fallback_suggestion,
        "status": "draft",
        "llm_fallback_used": True,
        "llm_error": "Background generation in progress",
    }