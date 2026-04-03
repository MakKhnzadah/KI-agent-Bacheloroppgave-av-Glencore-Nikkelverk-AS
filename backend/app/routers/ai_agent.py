import re
import logging
from typing import Literal, Optional
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT

router = APIRouter(prefix="/agent", tags=["AI Agent"])
logger = logging.getLogger(__name__)

class DocumentRequest(BaseModel):
    text: str


class ReviseRequest(BaseModel):
    document: str
    instruction: str


class ReviseResponse(BaseModel):
    message: str
    updated_document: str


class KbChatTurn(BaseModel):
    role: Literal["user", "bot"]
    message: str


class KnowledgeChatRequest(BaseModel):
    message: str
    category: Optional[str] = None
    history: Optional[list[KbChatTurn]] = None


class KnowledgeSource(BaseModel):
    id: str
    title: str
    author: str
    date: str
    category: str
    retrievalMethod: Literal["vector", "lexical"] = "lexical"


class KnowledgeChatResponse(BaseModel):
    answer: str
    sources: list[KnowledgeSource]

llm = OllamaProvider()
agent = AgentService(llm)


_KB_CHAT_PROMPT = """
Du er en KI-assistent for en intern kunnskapsbank.

Regler:
- Svar alltid på norsk (bokmål).
- Svar basert på kildene som er gitt under. Hvis kildene ikke inneholder nok informasjon, si tydelig at du ikke finner svaret i kunnskapsbanken.
- Vær konkret og praktisk.
- Ikke dikt opp detaljer.
""".strip()


_REVISION_PROMPT = """
Du er en hjelpsom assistent som redigerer et Markdown-dokument basert på brukerens instruksjon.

VIKTIG:
- Svar alltid på norsk (bokmål).
- Du MÅ returnere HELE det oppdaterte Markdown-dokumentet.
- Bevar YAML front matter (--- ... ---) hvis det finnes.
- Gjør kun endringer som følger av instruksjonen (ikke finn på ekstra innhold).
- Ikke legg inn forklaringer/kommentarer inni dokumentet.
- Ikke kopier/lim inn selve instruksjonsteksten i dokumentet.

FORBUDT SVARSTIL (må aldri skje):
- Ikke skriv "I'd be happy to help...", "Before we begin..." eller still avklaringsspørsmål.
- Anta at instruksjonen gjelder det vedlagte dokumentet og utfør endringen direkte.
- Ikke svar som en samtale; du skal levere MESSAGE + UPDATED_DOCUMENT.

- Hvis instruksjonen er et metaspørsmål om hva du kan gjøre (f.eks. "hva kan du gjøre?"), så:
    - Svar på spørsmålet i MESSAGE.
    - La UPDATED_DOCUMENT være uendret (returner dokumentet slik det var).

- Hvis instruksjonen ber om en ny versjon/omskriving (f.eks. "gi meg et nytt forslag", "skriv om", "omformuler"), så:
    - Lever en alternativ formulering av hele dokumentet.
    - Behold samme struktur, metadata og tema, men endre ordlyd så det faktisk blir en ny versjon.

LESBARHET (gjelder spesielt for lange dokumenter):
- Formater UPDATED_DOCUMENT som ryddig Markdown slik at det er lett å lese i UI.
- Hvis dokumentet er langt, skal det som minimum ha:
        - `# Tittel` (bruk YAML `title` hvis den finnes)
        - `## Kapittel`-seksjoner og `### Underkapittel` der det er naturlig
    - Behold kapittel-/seksjonsnummer hvis de finnes i teksten (f.eks. `## 1 Innledning`, `### 1.1 Bakgrunn`, `## 2 Teori`).
        - korte avsnitt (2-5 setninger) med blank linje mellom
        - punktlister der det passer
- Du kan omstrukturere for lesbarhet (overskrifter/avsnitt/lister) uten å endre fakta eller mening.
- Ikke legg til nye fakta, nye påstander eller nye avsnitt som ikke finnes i kildeteksten.

PDF/PLAIN-TEXT OPPRYDDING (uten å endre innhold):
- Fjern/ignorer sidemarkører og layout-støy som "Page 12", enslige romertall (i, ii, iii), og dot-leaders i innholdsfortegnelse (". . .").
- Hvis du ser dupliserte overskrifter på samme linje (f.eks. "2 THEORY 2 Theory"), behold kun én ryddig overskrift.
- Fiks linjedeling med bindestrek fra PDF ("in-\ncluding" -> "including").
- Sett inn manglende mellomrom mellom ord hvis de er "limt" sammen.
- Bevar tabeller/figurer/listetabeller som tekst, men formater dem ryddig.

STRUKTURMAL (bruk når teksten er flat/ustukturert):
- Start med `# <Tittel>`.
- Deretter `## Sammendrag/Abstract` hvis relevant.
- Bruk `##` for hoveddeler (Innledning, Teori, Metode, Resultat, Diskusjon, Konklusjon, Referanser).
- Bruk `###` for underseksjoner (f.eks. 1.1, 2.3 osv.).
- Unngå å gjenta "Contents/List of Figures/List of Tables" med sidetall; hvis du tar dem med, fjern sidetall og gjør dem kompakte.

Output-format (eksakte markører):
MESSAGE:\n<kort svar til brukeren>\n\nUPDATED_DOCUMENT:\n<fullt oppdatert markdown>
""".strip()


_LONG_DOC_READABILITY_HINT = """
EKSTRA KRAV FOR LESBARHET:
- Dokumentet du får kan være langt og/eller uten tydelig struktur.
- Du skal gjøre UPDATED_DOCUMENT leselig ved å legge til strukturert Markdown:
    - `#` for tittel, `##` for hovedseksjoner, `###` for underseksjoner.
    - korte avsnitt og punktlister der det passer.
- Bevar innhold og mening; ikke dikt opp nye fakta.
""".strip()


_GLUED_PDF_TEXT_HINT = """
EKSTRA KRAV FOR PDF-TEKST:
- Dokumentet kan inneholde tekst der ord er "limt" sammen eller linjebrutt på rare steder pga. PDF-ekstraksjon (f.eks. "in- cluding", manglende mellomrom, lange sammenhengende ord).
- Du skal gjøre teksten leselig ved å:
    - sette inn naturlige mellomrom mellom ord
    - normalisere linjeskift og avsnitt
    - fjerne linjedelingsbindestreker der ord er delt ("in-\ncluding" -> "including")
- IKKE endre fakta, tall, navn, forkortelser eller fagtermer. Ikke oppsummer og ikke omskriv innholdet til noe annet.
""".strip()


_MSG_MARKER = "MESSAGE:"
_DOC_MARKER = "UPDATED_DOCUMENT:"


def _looks_like_document_text(text: str) -> bool:
    """Heuristic: determine whether a model output looks like a document draft.

    Used only when the model fails to follow our MESSAGE/UPDATED_DOCUMENT markers.
    We prefer being conservative to avoid polluting stored drafts with chatty replies.
    """

    t = (text or "").strip().replace("\r\n", "\n")
    if not t:
        return False

    # Strong signals for a document: YAML front matter or Markdown headings.
    if t.startswith("---\n"):
        return True
    if re.search(r"(?m)^#{1,6}\s+\S", t):
        return True

    # Numbered headings like "1 Introduction".
    if re.search(r"(?m)^\d+(?:\.\d+)*\s+\S", t):
        return True

    # Multi-paragraph / multi-line content is more likely a document than a short chat reply.
    if t.count("\n") >= 12 and len(t) >= 1200:
        return True

    return False


def _looks_like_chatty_reply(text: str) -> bool:
    """Heuristic: detect assistant-style conversational replies.

    This catches outputs like "I'd be happy to help..." that should go to MESSAGE.
    """

    t = (text or "").strip()
    if not t:
        return False

    # Common assistant boilerplate (English + Norwegian).
    if re.search(r"(?i)\b(i\s*['’]d\s+be\s+happy\s+to\s+help|before\s+we\s+begin|please\s+confirm|do\s+you\s+have\s+any\s+particular|is\s+that\s+correct)\b", t):
        return True
    if re.search(r"(?i)\bkan\s+du\s+si\s+mer|før\s+vi\s+begynner|har\s+du\s+noen\s+preferanser|er\s+det\s+korrekt\b", t):
        return True

    # Lots of questions in a relatively short answer is likely chat.
    if t.count("?") >= 2 and len(t) < 2500:
        return True

    return False


def _strip_wrapper_lines(text: str) -> str:
    """Remove our own wrapper tags/labels if the model accidentally echoes them in UPDATED_DOCUMENT."""

    if not text:
        return ""

    lines: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        upper = s.upper()
        if upper in {"<DOCUMENT>", "</DOCUMENT>", "<INSTRUCTION>", "</INSTRUCTION>"}:
            continue
        if re.match(r"^(CURRENT_DOCUMENT|INSTRUCTION)\s*:\s*$", upper):
            continue
        lines.append(line)

    return "\n".join(lines).strip()


def _instruction_requests_rewrite(instruction: str) -> bool:
    text = (instruction or "").strip().lower()
    if not text:
        return False

    patterns = [
        r"\bnytt\s+forslag\b",
        r"\bny\s+versjon\b",
        r"\bomskriv\b",
        r"\bskriv\s+om\b",
        r"\bomformuler\b",
        r"\balternativ\b",
        r"\bgenerer\b.*\bny\b",
        r"\blag\b.*\bny\b",
        r"\bfjern\b.*\blikhet",
        r"\bfjern\b.*\boverlapp",
        r"\bunngå\b.*\blikhet",
        r"\bunngå\b.*\boverlapp",
        r"\bmer\s+unik\b",
    ]

    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _doc_needs_readability_structuring(doc: str) -> bool:
    text = (doc or "").replace("\r\n", "\n").strip()
    if not text:
        return False

    is_long = len(text) >= 6000 or text.count("\n") >= 180
    if not is_long:
        return False

    has_headings = bool(re.search(r"(?m)^#{1,6}\s+\S", text))
    has_paragraphs = "\n\n" in text
    has_lists = bool(re.search(r"(?m)^\s*([-*+]\s+\S|\d+\.\s+\S)", text))

    # If it already looks structured, don't force additional restructuring.
    return not (has_headings and (has_paragraphs or has_lists))


def _doc_looks_like_glued_pdf_text(doc: str) -> bool:
    """Detect PDF extraction artifacts where spacing is largely missing.

    Used only to add an extra instruction to the LLM; we don't mutate stored content here.
    """

    text = (doc or "").replace("\r\n", "\n").strip()
    if len(text) < 400:
        return False

    sample = re.sub(r"\s+", " ", text).strip()
    if len(sample) < 400:
        return False

    words = [w for w in sample.split(" ") if w]
    if not words:
        return False

    avg_len = sum(len(w) for w in words) / len(words)
    long_tokens = sum(1 for w in words if len(w) >= 40)
    space_ratio = sample.count(" ") / max(1, len(sample))

    return long_tokens >= 8 or (space_ratio < 0.055 and avg_len > 11)


def _looks_like_prompt_echo(doc: str) -> bool:
    text = doc or ""
    # If the model repeats our input wrapper, never write that into the document.
    # Match wrapper markers as standalone prefixes/tags to avoid false positives.
    if re.search(r"(?im)^\s*(CURRENT_DOCUMENT|INSTRUCTION)\s*:", text):
        return True
    if re.search(r"(?im)<\/?\s*DOCUMENT\s*>", text):
        return True
    if re.search(r"(?im)<\/?\s*INSTRUCTION\s*>", text):
        return True
    return False


def _parse_revision_output(text: str, *, fallback_document: str) -> tuple[str, str]:
    raw = (text or "").strip()
    raw = raw.replace("\r\n", "\n")

    # Remove common markdown fencing if the model wraps output.
    if raw.startswith("```") and raw.endswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", raw)
        raw = raw[:-3].strip()

    # If the model only returned a MESSAGE block, treat it as chat-only and keep document unchanged.
    if _MSG_MARKER in raw and _DOC_MARKER not in raw:
        msg_only = raw.split(_MSG_MARKER, 1)[1].strip()
        if msg_only:
            return msg_only, fallback_document

    if _DOC_MARKER in raw:
        before, after = raw.split(_DOC_MARKER, 1)
        msg = before.replace(_MSG_MARKER, "").strip() if _MSG_MARKER in before else before.strip()
        doc = _strip_wrapper_lines(after.strip())
        if doc:
            if _looks_like_prompt_echo(doc):
                return "Jeg fikk et uventet svar fra modellen og gjorde ingen endringer.", fallback_document
            return (msg or "Oppdatert dokumentet."), doc

    # Fallback: if the model didn't follow the required markers, keep the document unchanged.
    # This avoids polluting the KB draft with prompt echoes.
    if _looks_like_prompt_echo(raw) or not raw:
        return "Jeg klarte ikke å tolke svaret fra modellen, så dokumentet ble ikke endret.", fallback_document

    # If the model ignored the required markers, decide whether it's a chat reply or a document.
    # Prefer treating it as a MESSAGE (chat) unless it strongly looks like a document.
    if _looks_like_chatty_reply(raw) and not _looks_like_document_text(raw):
        return raw.strip(), fallback_document

    if _looks_like_document_text(raw) and not _looks_like_chatty_reply(raw):
        return "Oppdatert dokumentet.", raw

    # Conservative default: surface the model output as MESSAGE and keep document unchanged.
    return raw.strip(), fallback_document


def _sanitize_updated_document(doc: str, instruction: str) -> str:
    """Best-effort cleanup to prevent prompt/instruction echo entering the document."""

    text = (doc or "").replace("\r\n", "\n")
    instr = (instruction or "").strip()

    # Remove a trailing prompt-echo block if the model appended it.
    # We only truncate when it looks like our wrapper (labels/tags) or appears near the end.
    lines = text.split("\n")
    cut_idx = None
    for i, line in enumerate(lines):
        s = line.strip().upper()
        if s.startswith("INSTRUCTION:") or s.startswith("CURRENT_DOCUMENT:"):
            cut_idx = i
            break
        if s.startswith("<INSTRUCTION>") or s.startswith("<DOCUMENT>"):
            cut_idx = i
            break

    if cut_idx is not None:
        tail = "\n".join(lines[cut_idx:]).upper()
        is_prompt_echo_tail = (
            "CURRENT_DOCUMENT:" in tail
            or "INSTRUCTION:" in tail
            or "<DOCUMENT>" in tail
            or "<INSTRUCTION>" in tail
        )
        is_near_end = (len(lines) - cut_idx) <= 160
        if is_prompt_echo_tail or is_near_end:
            lines = lines[:cut_idx]

    text = "\n".join(lines).rstrip() + "\n"

    # If the model inserted the exact instruction as a standalone line near the top, remove it.
    if instr:
        out_lines: list[str] = []
        removed_once = False
        scan_limit = 80  # only sanitize early portion to avoid removing legitimate content deep in the doc
        for idx, line in enumerate(text.split("\n")):
            if not removed_once and idx < scan_limit and line.strip().lower() == instr.lower():
                removed_once = True
                continue
            out_lines.append(line)
        text = "\n".join(out_lines).rstrip() + "\n"

    return text


def _kb_rel_path_from_vector_meta(meta: dict) -> Optional[str]:
    raw_path = str((meta or {}).get("path") or "").strip()
    if not raw_path:
        return None

    try:
        from app.vector_store.config import _repo_root_from_here

        repo_root = Path(_repo_root_from_here())
        kb_root = (repo_root / "databases" / "knowledge_base" / "raw").resolve()
        full = Path(raw_path)
        if not full.is_absolute():
            full = (repo_root / full).resolve()
        else:
            full = full.resolve()
        return full.relative_to(kb_root).as_posix()
    except Exception:
        return None


def _vector_retrieve(msg: str, category: Optional[str], *, limit: int = 3) -> tuple[list[KnowledgeSource], list[str], Optional[str]]:
    try:
        from app.vector_store.chroma_store import ChromaVectorStore
        from app.vector_store.config import load_vector_store_config
        from app.vector_store.ollama_embeddings import OllamaEmbeddingClient
        from app.kb.kb_reader import get_kb_doc
    except Exception as exc:
        return [], [], f"Vector search unavailable: {exc}"

    try:
        cfg = load_vector_store_config()
        store = ChromaVectorStore(persist_dir=cfg.persist_dir, collection_name=cfg.chroma_collection)
        embedder = OllamaEmbeddingClient(
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_embed_model,
            timeout_s=cfg.ollama_embed_timeout_s,
        )

        query_embedding = embedder.embed_text(msg)
        res = store.query(query_embedding=query_embedding, n_results=max(3, min(limit * 3, 12)))
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]

        wanted_category = (category or "").strip()
        seen: set[str] = set()
        sources: list[KnowledgeSource] = []
        excerpts: list[str] = []

        for i, chunk in enumerate(docs):
            if len(sources) >= limit:
                break

            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            kb_rel_path = _kb_rel_path_from_vector_meta(meta)
            if not kb_rel_path or kb_rel_path in seen:
                continue

            try:
                kb_doc = get_kb_doc(kb_rel_path)
            except Exception:
                continue

            if wanted_category and wanted_category != "All" and kb_doc.category != wanted_category:
                continue

            seen.add(kb_rel_path)
            sources.append(
                KnowledgeSource(
                    id=kb_doc.kb_path,
                    title=kb_doc.title,
                    author=kb_doc.author,
                    date=kb_doc.date,
                    category=kb_doc.category,
                    retrievalMethod="vector",
                )
            )

            excerpt = (chunk or "").strip()
            excerpt = re.sub(r"\n{3,}", "\n\n", excerpt)
            excerpt = excerpt[:1500]
            excerpts.append(
                "\n".join(
                    [
                        f"KILDE: {kb_doc.title}",
                        f"PATH: {kb_doc.kb_path}",
                        f"KATEGORI: {kb_doc.category}",
                        "METODE: vector",
                        "UTDRAG:",
                        excerpt,
                    ]
                )
            )

        return sources, excerpts, None
    except Exception as exc:
        return [], [], f"Vector retrieval failed: {exc}"

@router.post("/process")
def process_document(request: DocumentRequest):
    result = agent.process_document(STRUCTURING_AGENT_PROMPT, request.text)
    return {"result": result}


@router.post("/revise", response_model=ReviseResponse)
def revise_document(request: ReviseRequest) -> ReviseResponse:
    rewrite_hint = (
        "\n\nMERK: Instruksjonen ber om en ny/alternativ versjon. Du skal omskrive hele dokumentet.\n"
        if _instruction_requests_rewrite(request.instruction)
        else ""
    )

    readability_hint = (
        "\n\n" + _LONG_DOC_READABILITY_HINT + "\n"
        if _doc_needs_readability_structuring(request.document)
        else ""
    )

    glued_pdf_hint = (
        "\n\n" + _GLUED_PDF_TEXT_HINT + "\n"
        if _doc_looks_like_glued_pdf_text(request.document)
        else ""
    )

    # Use tags instead of label prefixes to reduce the chance of the model echoing the wrapper.
    prompt = (
        f"{_REVISION_PROMPT}{rewrite_hint}{readability_hint}{glued_pdf_hint}\n\n"
        f"<INSTRUCTION>\n{request.instruction}\n</INSTRUCTION>\n\n"
        f"<DOCUMENT>\n{request.document}\n</DOCUMENT>"
    )

    output = llm.generate(prompt)
    message, updated_document = _parse_revision_output(output, fallback_document=request.document)
    updated_document = _sanitize_updated_document(updated_document, request.instruction)
    return ReviseResponse(message=message, updated_document=updated_document)


@router.post("/knowledge-chat", response_model=KnowledgeChatResponse)
def knowledge_chat(request: KnowledgeChatRequest) -> KnowledgeChatResponse:
    """Chat/Q&A for the knowledge bank.

    Retrieval is dependency-free: simple lexical matching over KB markdown files.
    """

    from app.kb.kb_reader import search_kb, split_front_matter

    msg = (request.message or "").strip()
    if not msg:
        return KnowledgeChatResponse(answer="Skriv et spørsmål, så kan jeg prøve å finne svaret i kunnskapsbanken.", sources=[])

    vector_sources, vector_excerpts, vector_error = _vector_retrieve(msg, request.category, limit=3)

    sources: list[KnowledgeSource] = []
    excerpts: list[str] = []
    retrieval_mode = "vector"

    if vector_sources:
        sources = vector_sources
        excerpts = vector_excerpts
    else:
        docs = search_kb(msg, category=request.category, limit=3)
        sources = [
            KnowledgeSource(
                id=d.kb_path,
                title=d.title,
                author=d.author,
                date=d.date,
                category=d.category,
                retrievalMethod="lexical",
            )
            for d in docs
        ]
        retrieval_mode = "lexical"

        for d in docs:
            front, body = split_front_matter(d.content)
            excerpt = (body or "").strip()
            excerpt = re.sub(r"\n{3,}", "\n\n", excerpt)
            excerpt = excerpt[:1500]
            excerpts.append(
                "\n".join(
                    [
                        f"KILDE: {d.title}",
                        f"PATH: {d.kb_path}",
                        f"KATEGORI: {d.category}",
                        "METODE: lexical",
                        "UTDRAG:",
                        excerpt,
                    ]
                )
            )

    history_lines: list[str] = []
    if request.history:
        for turn in request.history[-8:]:
            role = "Bruker" if turn.role == "user" else "Assistent"
            content = (turn.message or "").strip()
            if not content:
                continue
            history_lines.append(f"{role}: {content}")

    context_block = "\n\n---\n\n".join(excerpts) if excerpts else "(Ingen kilder funnet.)"
    history_block = "\n".join(history_lines) if history_lines else "(Ingen historikk.)"
    retrieval_block = f"Hentemetode: {retrieval_mode}" + (f" (vector-feil: {vector_error})" if vector_error and retrieval_mode == "lexical" else "")

    prompt = (
        f"{_KB_CHAT_PROMPT}\n\n"
        f"{retrieval_block}\n\n"
        f"SAMTALEHISTORIKK:\n{history_block}\n\n"
        f"BRUKERSPØRSMÅL:\n{msg}\n\n"
        f"KILDER (markdown-utdrag):\n{context_block}\n\n"
        "Svar nå."
    )

    try:
        answer = llm.generate(prompt).strip()
    except Exception as exc:
        logger.exception("Knowledge chat generation failed")
        answer = "Jeg fikk ikke kontakt med språkmodellen akkurat nå. Prøv igjen."

    if not answer:
        answer = "Jeg fikk ikke et svar fra modellen akkurat nå. Prøv igjen."

    return KnowledgeChatResponse(answer=answer, sources=sources)