import os
import re
import logging
import requests
from bs4 import BeautifulSoup


class WHOScraper:
    """
        Scraper pour récupérer les fiches d'information de l'OMS (WHO Fact Sheets)
        et les enregistrer en fichiers texte dans un dossier local.
    """

    def __init__(self, base_url="https://www.who.int", output_dir="data"):
        self.base_url = base_url
        self.index_url = f"{self.base_url}/news-room/fact-sheets/"
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        self.logger = logging.getLogger("app.scrapper")
        self.logger.setLevel(logging.INFO)

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Nettoyer le texte (espaces et sauts de ligne multiples).
        """
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def get_fact_sheet_links(self):
        """
        Récupère tous les liens des fiches OMS depuis la page d'index.
        """
        self.logger.info("Récupération des liens de fiches OMS...")
        resp = requests.get(self.index_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        links = []

        for a in soup.select("a"):
            href = a.get("href")
            if href and "/news-room/fact-sheets/" in href and not href.endswith("fact-sheets/"):
                full = href if href.startswith("http") else self.base_url + href
                links.append(full)

        links = sorted(set(links))
        self.logger.info(f"{len(links)} fiches détectées.")
        return links

    def extract_article(self, url: str):
        """
        Extrait le texte principal d'une fiche OMS.
        """
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            article = soup.find("article", class_="sf-detail-body-wrapper")
            if not article:
                self.logger.warning(f"Pas d'article trouvé pour : {url}")
                return None

            blocks = []
            for elem in article.find_all(["h2", "h3", "p", "li"]):
                txt = self.clean_text(elem.get_text(" ", strip=True))
                if txt:
                    if elem.name == "li":
                        blocks.append(f"- {txt}")
                    else:
                        blocks.append(txt)

            title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "untitled"
            content = "\n\n".join(blocks)
            return title, content

        except Exception as e:
            self.logger.error(f"Erreur sur {url}: {e}")
            return None

    def build_txt_corpus(self):
        """
        Construit et sauvegarde toutes les fiches OMS dans des fichiers texte.
        """
        links = self.get_fact_sheet_links()
        for i, link in enumerate(links, 1):
            data = self.extract_article(link)
            if data:
                title, content = data
                filename = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.lower())[:80] + ".txt"
                filepath = os.path.join(self.output_dir, filename)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(title + "\n\n" + content)

                self.logger.info(f"{i}/{len(links)} - Sauvegardé : {filepath}")

        self.logger.info("Scraping terminé avec succès.")
