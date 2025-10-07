import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.data_preparation.parsers.txt_parser import TxtParser

def test_list_txt_files(tmp_path):
    # Crée des fichiers texte temporaires
    (tmp_path / "file1.txt").write_text("Contenu du fichier 1")
    (tmp_path / "file2.txt").write_text("Contenu du fichier 2")
    (tmp_path / "not_a_text.doc").write_text("Ceci n'est pas un fichier texte")

    parser = TxtParser(data_dir=tmp_path)
    files = parser.list_txt_files()
    assert len(files) == 2
    assert all(f.endswith(".txt") for f in files)

def test_clean_text():
    raw_text = "Ceci   est un   test.\n\n\nAvec des espaces   multiples.\n\n"
    cleaned = TxtParser.clean_text(raw_text)
    expected = "Ceci est un test.\n\nAvec des espaces multiples."
    assert cleaned == expected

def test_parse_txt(tmp_path):
    """Teste la lecture et le nettoyage d’un fichier texte."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Some text   with  spaces", encoding="utf-8")

    parser = TxtParser(data_dir=str(tmp_path))
    text = parser.parse_txt(str(file_path))
    assert "  " not in text
    assert "Some text" in text

def test_load_corpus(tmp_path):
    """Teste le chargement complet d’un corpus."""
    (tmp_path / "doc1.txt").write_text("File one")
    (tmp_path / "doc2.txt").write_text("File two")

    parser = TxtParser(data_dir=str(tmp_path))
    corpus = parser.load_corpus()

    assert len(corpus) == 2
    assert all("title" in doc for doc in corpus)
    assert all("content" in doc for doc in corpus)
    assert all("path" in doc for doc in corpus)