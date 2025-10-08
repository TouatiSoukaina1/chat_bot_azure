import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile

from backend.app.data_preparation.scrapping import WHOScraper


class TestWHOScraper(unittest.TestCase):
    """Tests unitaires pour la classe WHOScraper"""

    def setUp(self):
        """Création d’un répertoire temporaire"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = self.temp_dir.name
        self.scraper = WHOScraper(output_dir=self.output_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- TESTS __INIT__ ---
    def test_init_creates_output_dir(self):
        """Le dossier de sortie est bien créé"""
        self.assertTrue(os.path.exists(self.output_dir))
        self.assertTrue(self.scraper.index_url.endswith("/news-room/fact-sheets/"))

    # --- TEST clean_text ---
    def test_clean_text(self):
        """Nettoyage du texte : espaces multiples, sauts de ligne"""
        dirty = "Texte   avec \n\n  espaces   multiples"
        cleaned = WHOScraper.clean_text(dirty)
        self.assertEqual(cleaned, "Texte avec espaces multiples")

    # --- TEST get_fact_sheet_links ---
    @patch("backend.app.data_preparation.scrapping.requests.get")
    def test_get_fact_sheet_links(self, mock_get):
        """Extraction correcte des liens de fiches OMS"""
        html = """
        <html><body>
            <a href="/news-room/fact-sheets/detail/malaria">Malaria</a>
            <a href="/news-room/fact-sheets/detail/covid-19">COVID</a>
            <a href="/news-room/fact-sheets/">Index</a>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        links = self.scraper.get_fact_sheet_links()

        self.assertEqual(len(links), 2)
        self.assertTrue(all(link.startswith("https://www.who.int") for link in links))
        mock_get.assert_called_once_with(self.scraper.index_url)

    # --- TEST extract_article ---
    @patch("backend.app.data_preparation.scrapping.requests.get")
    def test_extract_article_success(self, mock_get):
        """Extraction réussie du contenu d’un article"""
        html = """
        <html>
            <h1>COVID-19</h1>
            <article class="sf-detail-body-wrapper">
                <h2>Overview</h2>
                <p>COVID-19 is a disease.</p>
                <ul><li>Spread by droplets</li></ul>
            </article>
        </html>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.scraper.extract_article("https://www.who.int/fake")

        self.assertIsInstance(result, tuple)
        title, content = result
        self.assertIn("COVID-19", title)
        self.assertIn("Spread by droplets", content)

    @patch("backend.app.data_preparation.scrapping.requests.get")
    def test_extract_article_no_article(self, mock_get):
        """Retourne None si aucun article trouvé"""
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Titre</h1></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.scraper.extract_article("https://www.who.int/no-article")
        self.assertIsNone(result)

    @patch("backend.app.data_preparation.scrapping.requests.get")
    def test_extract_article_exception(self, mock_get):
        """Retourne None en cas d’erreur réseau"""
        mock_get.side_effect = Exception("Erreur réseau simulée")
        result = self.scraper.extract_article("https://www.who.int/error")
        self.assertIsNone(result)

    # --- TEST build_txt_corpus ---
    @patch.object(WHOScraper, "get_fact_sheet_links")
    @patch.object(WHOScraper, "extract_article")
    @patch("builtins.open", new_callable=mock_open)
    def test_build_txt_corpus(self, mock_file, mock_extract, mock_links):
        """Sauvegarde correcte des fiches en fichiers texte"""
        mock_links.return_value = [
            "https://www.who.int/fact1",
            "https://www.who.int/fact2"
        ]
        mock_extract.side_effect = [
            ("Fact 1", "Contenu 1"),
            ("Fact 2", "Contenu 2")
        ]

        self.scraper.build_txt_corpus()

        self.assertEqual(mock_extract.call_count, 2)
        self.assertTrue(mock_file.called)
        mock_file.assert_any_call(
            os.path.join(self.output_dir, "fact_1.txt"),
            "w",
            encoding="utf-8"
        )

    @patch.object(WHOScraper, "get_fact_sheet_links", return_value=[])
    def test_build_txt_corpus_no_links(self, mock_links):
        """Aucun lien → aucun appel à extract_article"""
        with patch.object(WHOScraper, "extract_article") as mock_extract:
            self.scraper.build_txt_corpus()
            mock_extract.assert_not_called()
