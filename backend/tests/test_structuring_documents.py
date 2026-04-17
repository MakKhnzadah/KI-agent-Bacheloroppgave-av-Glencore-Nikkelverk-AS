import re

from app.services import revised_suggestion as rs


def test_extract_abstract_supports_sammendrag() -> None:
    text = (
        "Tittel\n"
        "Sammendrag: Dette dokumentet beskriver krav til personlig verneutstyr.\n"
        "Det gjelder for alle ansatte.\n\n"
        "1. Innledning\nHer starter resten.\n"
    )
    abstract = rs.extract_abstract(text)
    assert abstract is not None
    assert "personlig verneutstyr" in abstract
    assert "Innledning" not in abstract


def test_extract_conclusion_supports_konklusjon() -> None:
    text = (
        "...\n\n"
        "5 Konklusjon\n"
        "Dette er hovedkonklusjonen.\n"
        "Den gjelder umiddelbart.\n\n"
        "Referanser\n[1] ...\n"
    )
    conclusion = rs.extract_conclusion(text)
    assert conclusion is not None
    assert "hovedkonklusjonen" in conclusion
    assert "Referanser" not in conclusion


def test_strip_leading_table_of_contents_removes_toc_block() -> None:
    # Needs >= 40 lines for the heuristic to consider stripping.
    toc_lines = [
        "Innhold",
        "1 Innledning 1",
        "1.1 Formål 2",
        "2 Krav 3",
        "3 Roller 4",
    ] + [f"{i} Vedlegg {i}" for i in range(4, 55)]

    body_lines = [
        "",
        "# Håndbok PA",
        "",
        "## Kort sammendrag",
        "- Dette er selve innholdet.",
    ]

    text = "\n".join(toc_lines + body_lines)
    stripped = rs.strip_leading_table_of_contents(text)

    assert "Innhold" not in stripped.splitlines()[:10]
    assert "# Håndbok PA" in stripped


def test_toc_only_structured_draft_is_used_for_toc_snippet() -> None:
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

    out = rs.toc_only_structured_draft("Håndbok PA.docx", toc)
    assert out.startswith("---\n")
    assert "## Kapittelvis sammendrag" in out
    assert "1.1 Ekstra påbud om verneutstyr" in out
    assert "(ikke oppgitt i utdraget)" in out


def test_render_yaml_markdown_includes_required_sections() -> None:
    payload = {
        "title": "Tittel",
        "tags": [],
        "category": "Annet",
        "review_status": "pending",
        "confidence_score": 0.5,
        "sections": {
            "Kort sammendrag": ["OK"],
            "Viktigste punkter": ["Punkt 1"],
            "Kapittelvis sammendrag": [],
            "Relevante detaljer": [],
            "Eventuelle tiltak / anbefalinger": [],
        },
    }
    out = rs.render_yaml_markdown(payload)

    assert out.startswith("---\n")
    assert re.search(r"(?m)^title:\s+", out)
    assert "# Tittel" in out
    assert "## Kort sammendrag" in out
    assert "## Viktigste punkter" in out


def test_fallback_structured_document_short_is_well_formed() -> None:
    out = rs.fallback_structured_document_short("Håndbok PA.docx", "Noe tekst her.")
    assert out.startswith("---\n")
    assert "review_status" in out
    assert "## Kort sammendrag" in out
