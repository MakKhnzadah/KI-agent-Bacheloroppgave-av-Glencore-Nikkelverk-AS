from app.services import revised_suggestion as rs


class _StubAgent:
    def process_document(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("LLM should not be called for TOC-only sources")


def test_generate_revised_suggestion_short_circuits_on_toc_only() -> None:
    toc = "\n".join(
        [
            "Innhold",
            "1 Helse og sikkerhet i PA-anlegget 2",
            "1.1 Ekstra påbud om verneutstyr 2",
            "1.2 Farlige stoffer 2",
            "1.3 Farekilder 2",
            "1.4 Håndtering av gassalarmer i PA 3",
            "2 Miljømessige forhold i PA 4",
            "2.1 Utslippskrav, målsettinger og kjeller/kaiforhold 4",
            "2.2 Utslipp til luft, sjø og akuttutslipp 5",
            "2.3 Kontroll og vedlikehold av utstyr og tiltak ved avvik 7",
            "3 Orientering PA-anlegget 9",
            "3.1 Bemanning, arbeidsordning og ansvar 9",
            "3.2 Viktige målinger og regulering i PA 10",
            "4 Felletrinn for avløpsvann 11",
        ]
    )

    out, diag = rs.generate_revised_suggestion(
        agent=_StubAgent(),
        original_filename="Håndbok PA.docx",
        extracted_text=toc,
        llm_options={},
    )

    assert diag["fallback_used"] == 1
    assert diag["reason"] == "toc_only"
    assert out.startswith("---\n")
    assert "## Kapittelvis sammendrag" in out
    assert "(ikke oppgitt i utdraget)" in out


def test_evidence_validation_requires_quote_in_source() -> None:
    source = "Dette er et utdrag med en viktig setning om sikkerhet."
    payload = {
        "title": "Tittel",
        "tags": [],
        "category": "Annet",
        "review_status": "pending",
        "confidence_score": 0.5,
        "sections": {
            "Kort sammendrag": [
                "Dette er en påstand (KILDE: \"viktig setning\")",
            ],
            "Viktigste punkter": [
                "(ikke oppgitt i utdraget)",
            ],
            "Kapittelvis sammendrag": [],
            "Relevante detaljer": [],
            "Eventuelle tiltak / anbefalinger": [],
        },
    }

    assert rs._validate_evidence(payload, source_pack=source) is None

    payload_bad = {
        **payload,
        "sections": {
            **payload["sections"],
            "Kort sammendrag": ["Dette mangler kilde"],
        },
    }
    assert rs._validate_evidence(payload_bad, source_pack=source) is not None


def test_evidence_validation_allows_whitespace_normalization() -> None:
    source = "Dette er et utdrag med en viktig\nsetning om sikkerhet."
    payload = {
        "title": "Tittel",
        "tags": [],
        "category": "Annet",
        "review_status": "pending",
        "confidence_score": 0.5,
        "sections": {
            "Kort sammendrag": [
                "Dette er en påstand (KILDE: \"viktig setning om sikkerhet\")",
            ],
            "Viktigste punkter": [
                "(ikke oppgitt i utdraget)",
            ],
            "Kapittelvis sammendrag": [],
            "Relevante detaljer": [],
            "Eventuelle tiltak / anbefalinger": [],
        },
    }

    assert rs._validate_evidence(payload, source_pack=source) is None


def test_repair_extraction_artifacts_joins_split_words() -> None:
    raw = "Dette er tilgjengeli\ng tekst og fraCO2-avdrivningstanken."
    fixed = rs.repair_extraction_artifacts(raw)
    assert "tilgjengelig" in fixed
    assert "fra CO2" in fixed


def test_repair_extraction_artifacts_joins_split_words_with_indent_and_sentence_space() -> None:
    raw = "Det vil normalt bare være behov for HCl når det ikke er gassrensesyre tilgjengeli\n g.Løsningen renner videre."
    fixed = rs.repair_extraction_artifacts(raw)
    assert "tilgjengelig" in fixed
    assert "tilgjengelig. Løsningen" in fixed


def test_repair_extraction_artifacts_normalizes_formulas() -> None:
    raw = "Klor (Cl 2), lutløsning (Na OH) og p H < 7 samt Na 2SO4 vedca 65 % nivå."
    fixed = rs.repair_extraction_artifacts(raw)
    assert "Cl2" in fixed
    assert "NaOH" in fixed
    assert "pH" in fixed
    assert "Na2SO4" in fixed
    assert "ved ca" in fixed


def test_sample_windows_snaps_to_word_boundary() -> None:
    cleaned = "AAAAA\n" + ("x" * 50) + " STARTORD slutt.\n" + ("y" * 200) + "\n"
    # Start inside the long 'x' run so the function must snap.
    out = rs.sample_windows(cleaned, windows=2, window_chars=40)
    assert out
    # Ensure chunks don't start with a partial word character sequence cut.
    for _label, chunk in out:
        assert not chunk.startswith("TORD")
