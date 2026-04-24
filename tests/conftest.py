import pytest
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.data_preparation.parsers.image_parser import DoctrOCR

@pytest.fixture(scope="session")
def ocr():
    """
    Fixture pour initialiser DoctrOCR une seule fois pour toute la session de tests.
    GPU désactivé pour éviter les problèmes en CI ou sur machines sans GPU.
    """
    return DoctrOCR(gpu=False)

@pytest.fixture
def tmp_image_file(tmp_path):
    """
    Fixture pour créer un faux fichier image temporaire.
    Retourne le chemin du fichier.
    """
    def _create(name="fake_image.png", content="fake content"):
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path
    return _create