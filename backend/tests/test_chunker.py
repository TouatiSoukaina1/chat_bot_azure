from app.data_preparation.processors.chunker import Chunker


def test_chunker_splits_markdown_sections():
    text = """
# Overview

This is the overview.

## Symptoms

Fever and rash.

## Treatment

Supportive care.
""".strip()

    chunker = Chunker(chunk_size=200, overlap=20)
    chunks = chunker.chunk_text(text, doc_title="Mpox")

    assert len(chunks) >= 2
    assert any(ch["section_title"] == "Overview" for ch in chunks)
    assert any(ch["section_title"] == "Symptoms" for ch in chunks)
    assert any(ch["section_title"] == "Treatment" for ch in chunks)


def test_chunker_fallback_without_headings():
    text = "This is a plain text document without markdown headings."

    chunker = Chunker(chunk_size=200, overlap=20)
    chunks = chunker.chunk_text(text, doc_title="Plain doc")

    assert len(chunks) >= 1
    assert chunks[0]["section_title"] == "Body"


def test_chunker_includes_doc_and_section_prefix():
    text = """
# Symptoms

Fever and rash.
""".strip()

    chunker = Chunker(chunk_size=200, overlap=20, include_section_prefix=True)
    chunks = chunker.chunk_text(text, doc_title="Mpox")

    assert len(chunks) == 1
    assert "[DOC] Mpox" in chunks[0]["text"]
    assert "[SECTION] Symptoms" in chunks[0]["text"]


def test_chunker_splits_long_section_into_multiple_chunks():
    paragraph = "This is a long paragraph about symptoms and treatment. " * 20
    text = f"# Symptoms\n\n{paragraph}\n\n{paragraph}"

    chunker = Chunker(chunk_size=250, overlap=50)
    chunks = chunker.chunk_text(text, doc_title="Mpox")

    assert len(chunks) > 1
    assert all(ch["section_title"] == "Symptoms" for ch in chunks)