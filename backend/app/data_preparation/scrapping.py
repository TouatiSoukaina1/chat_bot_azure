import requests
from bs4 import BeautifulSoup
import os
import re

BASE_URL = "https://www.who.int"
INDEX_URL = f"{BASE_URL}/news-room/fact-sheets/"
OUTPUT_DIR = os.path.join(os.getcwd(), "data") 

def clean_text(text: str) -> str:
    '''
        Nettoyer le texte (espaces, retours à la ligne inutiles).
    '''
    text = re.sub(r"\s+", " ", text)  
    return text.strip()

def get_fact_sheet_links():
    '''
        Récupère tous les liens de fiches OMS depuis la page d'index.
    '''
    resp = requests.get(INDEX_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.select("a"):
        href = a.get("href")
        if href and "/news-room/fact-sheets/" in href and not href.endswith("fact-sheets/"):
            full = href if href.startswith("http") else BASE_URL + href
            links.append(full)
    return sorted(set(links))

def extract_article(url):
    '''
        Extraction de l'article principal d'une fiche OMS.
    '''
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        article = soup.find("article", class_="sf-detail-body-wrapper")
        if not article:
            print("Pas d'article trouvé pour :", url)
            return None

        blocks = []
        for elem in article.find_all(["h2", "h3", "p", "li"]):
            txt = clean_text(elem.get_text(" ", strip=True))
            if txt:
                # si c'est un <li>, on garde une puce " - "
                if elem.name == "li":
                    blocks.append(f"- {txt}")
                else:
                    blocks.append(txt)

        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "untitled"
        return title, "\n\n".join(blocks)

    except Exception as e:
        print(f"Erreur sur {url} : {e}")
        return None

def build_txt_corpus():
    '''
        Construit un corpus en fichiers texte dans "data"
    '''
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    links = get_fact_sheet_links()

    for i, link in enumerate(links, 1):
        data = extract_article(link)
        if data:
            title, content = data
            # Nettoyer le titre pour nom de fichier
            filename = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.lower())[:50] + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(title + "\n\n" + content)

            print(f"{i}/{len(links)} - Sauvegardé :", filepath)

if __name__ == "__main__":
    build_txt_corpus()