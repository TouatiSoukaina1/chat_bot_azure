import unittest
from unittest.mock import patch, MagicMock
import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.data_preparation.parsers.image_parser import DoctrOCR


def make_page(texts):
    """Crée une page factice pour DoctrOCR à partir d'une liste de textes"""
    words = [MagicMock(value=t) for t in texts]
    line = MagicMock()
    line.words = words
    block = MagicMock()
    block.lines = [line]
    page = MagicMock()
    page.blocks = [block]
    return page


class TestDoctrOCR(unittest.TestCase):
    """Tests unitaires pour la classe DoctrOCR"""

    def setUp(self):
        """Configuration avant chaque test"""
        # Mock du logger pour éviter les logs
        self.logger_patcher = patch('backend.app.data_preparation.parsers.image_parser.logging.getLogger')
        self.mock_logger = self.logger_patcher.start()

        # Mock du modèle OCR
        self.ocr_predictor_patcher = patch('backend.app.data_preparation.parsers.image_parser.ocr_predictor')
        self.mock_ocr_predictor = self.ocr_predictor_patcher.start()

        # Instance de DoctrOCR avec mocks
        self.ocr = DoctrOCR(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", gpu=False)

    def tearDown(self):
        """Nettoyage après chaque test"""
        self.logger_patcher.stop()
        self.ocr_predictor_patcher.stop()

    @patch('backend.app.data_preparation.parsers.image_parser.ocr_predictor')
    def test_init_with_custom_params(self, mock_predictor):
        ocr = DoctrOCR(det_arch="db_mobilenet_v3", reco_arch="crnn_mobilenet_v3", gpu=False)
        mock_predictor.assert_called_once_with(det_arch="db_mobilenet_v3", reco_arch="crnn_mobilenet_v3", pretrained=True)
        self.assertEqual(ocr.device, "cpu")

    @patch('backend.app.data_preparation.parsers.image_parser.DocumentFile')
    @patch('os.path.exists')
    def test_extract_text_success(self, mock_exists, mock_doc_file):
        mock_exists.return_value = True
        mock_page = make_page(["Bonjour", "monde"])
        mock_result = MagicMock()
        mock_result.pages = [mock_page]
        self.ocr.model.return_value = mock_result
        mock_doc_file.from_images.return_value = MagicMock()

        result = self.ocr.extract_text("test_image.png")
        self.assertEqual(result, "Bonjour monde")

    @patch('os.path.exists')
    def test_extract_text_file_not_found(self, mock_exists):
        mock_exists.return_value = False
        result = self.ocr.extract_text("nonexistent.png")
        self.assertEqual(result, "")

    @patch('backend.app.data_preparation.parsers.image_parser.DocumentFile')
    @patch('os.path.exists')
    def test_extract_text_invalid_image(self, mock_exists, mock_doc_file):
        mock_exists.return_value = True
        mock_doc_file.from_images.return_value = None
        result = self.ocr.extract_text("invalid_image.png")
        self.assertEqual(result, "")

    @patch('backend.app.data_preparation.parsers.image_parser.DocumentFile')
    @patch('os.path.exists')
    def test_extract_text_no_text_detected(self, mock_exists, mock_doc_file):
        mock_exists.return_value = True
        empty_page = MagicMock()
        empty_page.blocks = []
        mock_result = MagicMock()
        mock_result.pages = [empty_page]
        self.ocr.model.return_value = mock_result
        mock_doc_file.from_images.return_value = MagicMock()
        result = self.ocr.extract_text("empty_image.png")
        self.assertEqual(result, "")

    @patch('backend.app.data_preparation.parsers.image_parser.DocumentFile')
    @patch('os.path.exists')
    def test_extract_text_multiple_pages(self, mock_exists, mock_doc_file):
        mock_exists.return_value = True
        page1 = make_page(["Page", "1"])
        page2 = make_page(["Page", "2"])
        mock_result = MagicMock()
        mock_result.pages = [page1, page2]
        self.ocr.model.return_value = mock_result
        mock_doc_file.from_images.return_value = MagicMock()
        result = self.ocr.extract_text("multi_page.pdf")
        self.assertEqual(result, "Page 1\nPage 2")

    @patch('backend.app.data_preparation.parsers.image_parser.DocumentFile')
    @patch('os.path.exists')
    def test_extract_text_exception_handling(self, mock_exists, mock_doc_file):
        mock_exists.return_value = True
        mock_doc_file.from_images.side_effect = Exception("Erreur de lecture")
        result = self.ocr.extract_text("error_image.png")
        self.assertEqual(result, "")

    @patch.object(DoctrOCR, 'extract_text')
    def test_process_batch_success(self, mock_extract):
        image_paths = ["image1.png", "image2.png", "image3.png"]
        expected_texts = ["Texte 1", "Texte 2", "Texte 3"]
        mock_extract.side_effect = expected_texts
        result = self.ocr.process_batch(image_paths)
        self.assertEqual(result, dict(zip(image_paths, expected_texts)))
        self.assertEqual(mock_extract.call_count, 3)

    @patch.object(DoctrOCR, 'extract_text')
    def test_process_batch_empty_list(self, mock_extract):
        result = self.ocr.process_batch([])
        self.assertEqual(result, {})
        mock_extract.assert_not_called()

    @patch.object(DoctrOCR, 'extract_text')
    def test_process_batch_partial_failure(self, mock_extract):
        image_paths = ["image1.png", "image2.png", "image3.png"]
        mock_extract.side_effect = ["Texte 1", "", "Texte 3"]
        result = self.ocr.process_batch(image_paths)
        self.assertEqual(result["image1.png"], "Texte 1")
        self.assertEqual(result["image2.png"], "")
        self.assertEqual(result["image3.png"], "Texte 3")

    @patch('backend.app.data_preparation.parsers.image_parser.DocumentFile')
    @patch('os.path.exists')
    def test_extract_text_special_characters(self, mock_exists, mock_doc_file):
        mock_exists.return_value = True
        page = make_page(["Café", "àéèêë"])
        mock_result = MagicMock()
        mock_result.pages = [page]
        self.ocr.model.return_value = mock_result
        mock_doc_file.from_images.return_value = MagicMock()
        result = self.ocr.extract_text("special_chars.png")
        self.assertEqual(result, "Café àéèêë")
