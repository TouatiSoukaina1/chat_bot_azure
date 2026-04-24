import unittest
from unittest.mock import patch, MagicMock
from app.data_preparation.parsers.image_parser import DoctrOCR

class TestDoctrOCR(unittest.TestCase):

    def setUp(self):
        # On initialise la classe avec un chemin fictif
        self.parser = DoctrOCR(images_path="/fake/images/path")

    @patch("backend.app.data_preparation.parsers.image_parser.os.path.exists", return_value=True)
    @patch("backend.app.data_preparation.parsers.image_parser.DocumentFile.from_images")
    def test_extract_text_success(self, mock_from_images, mock_exists):
        """Test extraction de texte réussie"""

        # Mock de l'image
        mock_doc = MagicMock()
        mock_from_images.return_value = mock_doc

        # Mock de la sortie du modèle OCR
        mock_result = MagicMock()
        mock_word = MagicMock()
        mock_word.value = "Bonjour"
        mock_line = MagicMock()
        mock_line.words = [mock_word]
        mock_block = MagicMock()
        mock_block.lines = [mock_line]
        mock_page = MagicMock()
        mock_page.blocks = [mock_block]
        mock_result.pages = [mock_page]

        # On remplace self.model par un mock qui renvoie mock_result
        self.parser.model = MagicMock(return_value=mock_result)

        texte = self.parser.extract_text("/fake/images/path/img1.jpg", nettoyer=False)
        self.assertIn("Bonjour", texte)

    @patch("backend.app.data_preparation.parsers.image_parser.os.path.exists", return_value=False)
    def test_extract_text_file_not_found(self, mock_exists):
        """Test extraction sur un fichier introuvable"""
        texte = self.parser.extract_text("/fake/images/path/missing.jpg")
        self.assertEqual(texte, "")

    @patch("backend.app.data_preparation.parsers.image_parser.os.path.exists", return_value=True)
    @patch("backend.app.data_preparation.parsers.image_parser.DocumentFile.from_images")
    def test_process_batch(self, mock_from_images, mock_exists):
        """Test traitement batch d'images"""

        # Mock de l'image
        mock_doc = MagicMock()
        mock_from_images.return_value = mock_doc

        # Mock de la sortie du modèle OCR
        mock_result = MagicMock()
        mock_word = MagicMock()
        mock_word.value = "Texte"
        mock_line = MagicMock()
        mock_line.words = [mock_word]
        mock_block = MagicMock()
        mock_block.lines = [mock_line]
        mock_page = MagicMock()
        mock_page.blocks = [mock_block]
        mock_result.pages = [mock_page]

        # On remplace self.model par un mock
        self.parser.model = MagicMock(return_value=mock_result)

        # On mocke glob.glob pour renvoyer plusieurs "fichiers"
        with patch("backend.app.data_preparation.parsers.image_parser.glob.glob", return_value=[
            "/fake/images/path/img1.jpg",
            "/fake/images/path/img2.jpg"
        ]):
            results = self.parser.process_batch(nettoyer=False)

        self.assertEqual(len(results), 2)
        for text in results.values():
            self.assertIn("Texte", text)

if __name__ == "__main__":
    unittest.main()
