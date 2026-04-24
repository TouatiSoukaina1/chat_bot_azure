import unittest
import tempfile
import os
from app.data_preparation.parsers.txt_parser import TxtParser

class TestTxtParser(unittest.TestCase):
    def setUp(self):
        """Créer un dossier temporaire avec quelques fichiers texte"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file1_path = os.path.join(self.temp_dir.name, "file1.txt")
        self.file2_path = os.path.join(self.temp_dir.name, "file2.txt")
        
        with open(self.file1_path, "w", encoding="utf-8") as f:
            f.write("Hello  world\n\nThis  is  file1.")
        
        with open(self.file2_path, "w", encoding="utf-8") as f:
            f.write("Another   file\nwith  text.")

        self.parser = TxtParser(data_dir=self.temp_dir.name)

    def tearDown(self):
        """Nettoyer le dossier temporaire"""
        self.temp_dir.cleanup()

    def test_list_txt_files(self):
        files = self.parser.list_txt_files()
        self.assertIn(self.file1_path, files)
        self.assertIn(self.file2_path, files)
        self.assertEqual(len(files), 2)

    def test_clean_text(self):
        raw_text = "Hello  \n\n\nWorld  "
        cleaned = self.parser.clean_text(raw_text)
        self.assertEqual(cleaned, "Hello\n\nWorld")

    def test_parse_txt(self):
        text = self.parser.parse_txt(self.file1_path)
        self.assertEqual(text, "Hello world\n\nThis is file1.")

    def test_load_corpus(self):
        corpus = self.parser.load_corpus()
        # corpus doit être un dictionnaire {chemin: texte}
        self.assertIn(self.file1_path, corpus)
        self.assertIn(self.file2_path, corpus)
        self.assertEqual(corpus[self.file1_path], "Hello world\n\nThis is file1.")
        self.assertEqual(corpus[self.file2_path], "Another file\nwith text.")
        self.assertEqual(len(corpus), 2)

    def test_load_corpus_empty_dir(self):
        empty_parser = TxtParser(data_dir=tempfile.mkdtemp())
        corpus = empty_parser.load_corpus()
        self.assertEqual(corpus, {})