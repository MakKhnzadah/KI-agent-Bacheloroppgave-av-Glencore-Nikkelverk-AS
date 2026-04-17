from __future__ import annotations

import re
from typing import Callable, Pattern

SECTION_SHORT = "Kort sammendrag"
SECTION_KEY = "Viktigste punkter"
SECTION_CHAPTER = "Kapittelvis sammendrag"
SECTION_DETAILS = "Relevante detaljer"

CORE_SECTIONS = {SECTION_SHORT, SECTION_KEY}
POSTPROCESS_SECTIONS = [SECTION_SHORT, SECTION_KEY, SECTION_CHAPTER, SECTION_DETAILS]

_ACTION_SIGNAL_RE = re.compile(
    r"\b(skal|må|bor|bør|kan|krever|påbudt|forbudt|ansvar|sjekk|stopp|start|"
    r"reduser|vurder|sendes|holdes|kontroller|iverksettes|unngå|luftes)\b",
    flags=re.IGNORECASE,
)

_READMORE_PREFIXES = ("se ", "se også", "informasjon om", "generelle krav", "generelle regler")


def postprocess_payload_sections(
    payload: dict,
    *,
    evidence_re: Pattern[str],
    is_toc_line: Callable[[str], bool],
    missing_marker: str,
) -> dict:
    p = dict(payload or {})
    sections = p.get("sections")
    if not isinstance(sections, dict):
        return p

    def strip_evidence_suffix(item: str) -> str:
        s = str(item or "").strip()
        m = evidence_re.search(s)
        if m:
            return s[: m.start()].strip()
        return s

    def has_action_signal(item: str) -> bool:
        return bool(_ACTION_SIGNAL_RE.search(strip_evidence_suffix(item)))

    def is_reference_or_heading_like(item: str) -> bool:
        s = strip_evidence_suffix(item)
        if not s:
            return False
        if is_toc_line(s):
            return True
        if has_action_signal(s):
            return False

        if re.match(r"^\d+(?:\.\d+)*\s+\S+(?:\s+\S+){0,11}$", s):
            return True

        lower = s.lower()
        if lower.startswith(("se ", "ref", "sop", "hms", "andre sikkerhetsregler", "informasjon om")) and len(s) <= 140:
            return True

        words = re.findall(r"\b\w+\b", s, flags=re.UNICODE)
        has_sentence_punct = bool(re.search(r"[.;:]", s))
        if len(words) <= 6 and not has_sentence_punct:
            return True
        return False

    def is_plain_heading_label(item: str) -> bool:
        s = strip_evidence_suffix(item)
        if not s:
            return False
        if has_action_signal(s):
            return False
        if is_toc_line(s):
            return True

        words = re.findall(r"\b\w+\b", s, flags=re.UNICODE)
        has_sentence_punct = bool(re.search(r"[.;:]", s))
        has_parens = "(" in s or ")" in s
        if 2 <= len(words) <= 14 and not has_sentence_punct and not has_parens:
            return True
        return False

    def is_weak_core_line_without_evidence(item: str) -> bool:
        s = str(item or "").strip()
        if not s:
            return False
        if evidence_re.search(s):
            return False
        if has_action_signal(s):
            return False

        plain = strip_evidence_suffix(s)
        words = re.findall(r"\b\w+\b", plain, flags=re.UNICODE)
        if len(words) <= 12 and not re.search(r"[.;:()]", plain):
            return True
        return False

    def is_readmore_reference_line(item: str) -> bool:
        plain = strip_evidence_suffix(item)
        if not plain:
            return False
        if has_action_signal(plain):
            return False

        lower = plain.lower()
        if lower.startswith(_READMORE_PREFIXES):
            return True
        if "kan leses" in lower or "dok.sys" in lower or "dokumentstyring" in lower:
            return True
        if "håndbok" in lower and len(plain) <= 180:
            return True
        return False

    for name in POSTPROCESS_SECTIONS:
        items_raw = sections.get(name)
        if not isinstance(items_raw, list):
            continue

        items = [str(x).strip() for x in items_raw if str(x).strip()]
        if not items:
            sections[name] = items
            continue

        deduped: list[str] = []
        seen_keys: set[str] = set()
        for x in items:
            key = re.sub(r"\s+", " ", strip_evidence_suffix(x)).strip().casefold()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(x)
        items = deduped

        informative_count = sum(1 for x in items if x != missing_marker and len(strip_evidence_suffix(x)) >= 18)
        if informative_count >= 3:
            items = [x for x in items if x != missing_marker]

        ref_cap = 1 if name in CORE_SECTIONS else 2
        ref_seen = 0
        filtered: list[str] = []
        for x in items:
            if name in CORE_SECTIONS:
                if is_plain_heading_label(x) or is_weak_core_line_without_evidence(x) or is_readmore_reference_line(x):
                    continue
            if is_reference_or_heading_like(x):
                if ref_seen >= ref_cap:
                    continue
                ref_seen += 1
            filtered.append(x)
        items = filtered

        if name in CORE_SECTIONS:
            action_items = [x for x in items if has_action_signal(x)]
            other_items = [x for x in items if not has_action_signal(x)]
            items = action_items + other_items

        sections[name] = items

    p["sections"] = sections
    return p
