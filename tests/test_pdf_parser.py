import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from app.data_preparation.parsers.pdf_parser import PdfParser

class TestPdfParser(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("backend.app.data_preparation.parsers.pdf_parser.pdfplumber.open")
    def test_extract_text_success(self, mock_pdf_open):
        """Test extraction de texte depuis un PDF réussi"""
        mock_pdf = MagicMock()
        page_mock = MagicMock()
        page_mock.extract_text.return_value = "Bonjour monde"
        mock_pdf.pages = [page_mock]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        parser = PdfParser(self.pdf_dir)
        result = parser.extract_text("dummy.pdf")
        self.assertEqual(result, "Bonjour monde")

    @patch("backend.app.data_preparation.parsers.pdf_parser.pdfplumber.open")
    def test_extract_text_empty_pdf(self, mock_pdf_open):
        """Test extraction depuis un PDF vide"""
        mock_pdf = MagicMock()
        page_mock = MagicMock()
        page_mock.extract_text.return_value = None
        mock_pdf.pages = [page_mock]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        parser = PdfParser(self.pdf_dir)
        result = parser.extract_text("dummy.pdf")
        self.assertEqual(result, "")

    @patch("backend.app.data_preparation.parsers.pdf_parser.glob.glob")
    @patch.object(PdfParser, "extract_text")
    def test_process_directory_success(self, mock_extract_text, mock_glob):
        """Test traitement d’un répertoire contenant plusieurs PDF"""
        fake_files = [
            os.path.join(self.pdf_dir, "doc1.pdf"),
            os.path.join(self.pdf_dir, "doc2.pdf")
        ]
        mock_glob.return_value = fake_files
        mock_extract_text.side_effect = ["Texte 1", "Texte 2"]

        parser = PdfParser(self.pdf_dir)
        result = parser.process_directory()

        self.assertEqual(len(result), 2)
        self.assertIn(fake_files[0], result)
        self.assertIn(fake_files[1], result)
        self.assertEqual(result[fake_files[0]], "Texte 1")
        self.assertEqual(result[fake_files[1]], "Texte 2")

    @patch("backend.app.data_preparation.parsers.pdf_parser.glob.glob")
    @patch.object(PdfParser, "extract_text")
    def test_process_directory_partial_failure(self, mock_extract_text, mock_glob):
        """Test traitement partiel : certains fichiers vides"""
        fake_files = [
            os.path.join(self.pdf_dir, "a.pdf"),
            os.path.join(self.pdf_dir, "b.pdf"),
            os.path.join(self.pdf_dir, "c.pdf"),
        ]
        mock_glob.return_value = fake_files
        mock_extract_text.side_effect = ["Texte A", "", "Texte C"]  # b.pdf vide

        parser = PdfParser(self.pdf_dir)
        result = parser.process_directory()

        self.assertIn(fake_files[0], result)
        self.assertIn(fake_files[2], result)
        self.assertNotIn(fake_files[1], result)
        self.assertEqual(result[fake_files[0]], "Texte A")
        self.assertEqual(result[fake_files[2]], "Texte C")

    @patch("backend.app.data_preparation.parsers.pdf_parser.glob.glob")
    @patch.object(PdfParser, "extract_text")
    def test_process_directory_no_pdfs(self, mock_extract_text, mock_glob):
        """Test répertoire sans PDF"""
        mock_glob.return_value = []
        parser = PdfParser(self.pdf_dir)
        result = parser.process_directory()

        self.assertEqual(result, {})
        mock_extract_text.assert_not_called()
