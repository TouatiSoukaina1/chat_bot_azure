import fitz

from app.data_preparation.parsers import base_parser as base_parser_module
from app.data_preparation.parsers.txt_parser import TxtParser
from app.data_preparation.parsers.markdown_parser import MarkdownParser
from app.data_preparation.parsers.pdf_parser import PdfParser


class FakeRepo:
    def __init__(self):
        self.docs = []
        self.by_id = {}

    def get_document_by_id(self, doc_id, file_type):
        return self.by_id.get((doc_id, file_type))

    def insert_document(self, document):
        self.docs.append(document)
        self.by_id[(document["id"], document["file_type"])] = document


def make_parser_with_fake_repo(monkeypatch, parser_cls, fake_repo, **kwargs):
    monkeypatch.setattr(
        base_parser_module,
        "DocumentRepository",
        lambda: fake_repo,
    )
    return parser_cls(**kwargs)


def test_txt_parser_extracts_text_and_inserts_document(tmp_path, monkeypatch):
    file_path = tmp_path / "test_doc.txt"
    file_path.write_text("Hello world\n\nThis is a test.", encoding="utf-8")

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        TxtParser,
        fake_repo,
        kb="user",
        scope="private",
        owner_user_id="tenant123:user123",
        source_type="user_upload",
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 1
    assert len(fake_repo.docs) == 1

    doc = fake_repo.docs[0]
    assert doc["filename"] == "test_doc.txt"
    assert doc["title"] == "test doc"
    assert doc["file_type"] == "txt"
    assert doc["scope"] == "private"
    assert doc["owner_user_id"] == "tenant123:user123"
    assert doc["source_type"] == "user_upload"
    assert doc["status"] == "parsed"
    assert "Hello world" in doc["text_content"]
    assert doc["text_content"] == "Hello world\n\nThis is a test."
    assert doc["id"] == TxtParser._make_doc_id(str(file_path))
    assert doc["path"] == str(file_path)
    assert doc["kb"] == "user"
    assert doc["created_at"]
    assert doc["updated_at"]


def test_markdown_parser_extracts_text_and_inserts_document(tmp_path, monkeypatch):
    file_path = tmp_path / "guide.md"
    file_path.write_text("# Title\n\n## Symptoms\n\nFever and rash.", encoding="utf-8")

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        MarkdownParser,
        fake_repo,
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 1
    assert len(fake_repo.docs) == 1

    doc = fake_repo.docs[0]
    assert doc["filename"] == "guide.md"
    assert doc["title"] == "guide"
    assert doc["file_type"] == "md"
    assert doc["scope"] == "global"
    assert doc["owner_user_id"] is None
    assert doc["source_type"] == "who"
    assert "# Title" in doc["text_content"]
    assert "## Symptoms" in doc["text_content"]


def test_pdf_parser_extracts_text_and_inserts_document(tmp_path, monkeypatch):
    file_path = tmp_path / "sample.pdf"

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "PDF extraction works")
    pdf.save(str(file_path))
    pdf.close()

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        PdfParser,
        fake_repo,
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 1
    assert len(fake_repo.docs) == 1

    doc = fake_repo.docs[0]
    assert doc["filename"] == "sample.pdf"
    assert doc["title"] == "sample"
    assert doc["file_type"] == "pdf"
    assert "PDF extraction works" in doc["text_content"]


def test_parser_skips_existing_document(tmp_path, monkeypatch):
    file_path = tmp_path / "existing.txt"
    file_path.write_text("already there", encoding="utf-8")

    fake_repo = FakeRepo()

    doc_id = TxtParser._make_doc_id(str(file_path))
    fake_repo.by_id[(doc_id, "txt")] = {
        "id": doc_id,
        "file_type": "txt",
    }

    parser = make_parser_with_fake_repo(
        monkeypatch,
        TxtParser,
        fake_repo,
        kb="user",
        scope="private",
        owner_user_id="tenant123:user123",
        source_type="user_upload",
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 0
    assert fake_repo.docs == []


def test_txt_parser_returns_empty_string_when_file_missing(tmp_path, monkeypatch):
    file_path = tmp_path / "missing.txt"

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        TxtParser,
        fake_repo,
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 0
    assert fake_repo.docs == []


def test_markdown_parser_returns_empty_string_when_file_missing(tmp_path, monkeypatch):
    file_path = tmp_path / "missing.md"

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        MarkdownParser,
        fake_repo,
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 0
    assert fake_repo.docs == []


def test_txt_parser_fallback_latin1(tmp_path, monkeypatch):
    file_path = tmp_path / "latin1.txt"
    file_path.write_bytes("café".encode("latin-1"))

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        TxtParser,
        fake_repo,
        encoding="utf-8",
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 1
    assert len(fake_repo.docs) == 1
    assert fake_repo.docs[0]["text_content"] == "café"


def test_markdown_parser_fallback_latin1(tmp_path, monkeypatch):
    file_path = tmp_path / "latin1.md"
    file_path.write_bytes("# café".encode("latin-1"))

    fake_repo = FakeRepo()
    parser = make_parser_with_fake_repo(
        monkeypatch,
        MarkdownParser,
        fake_repo,
        encoding="utf-8",
    )

    inserted = parser.process_file([str(file_path)])

    assert inserted == 1
    assert len(fake_repo.docs) == 1
    assert fake_repo.docs[0]["text_content"] == "# café"