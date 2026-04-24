from app.data_preparation.parsers.base_parser import BaseParser
import os
import logging


class MarkdownParser(BaseParser):
    """
    Parseur pour fichiers Markdown (.md)
    """
    supported_extensions = [".md", ".markdown"]

    def __init__(
        self,
        encoding="utf-8",
        kb: str = "who",
        scope: str = "global",
        owner_user_id=None,
        source_type: str = "who",
    ):
        super().__init__(
            kb=kb,
            scope=scope,
            owner_user_id=owner_user_id,
            source_type=source_type,
        )
        self.encoding = encoding
        self.logger = logging.getLogger("app.markdownparser")
        self.logger.info("MarkdownParser initialisé.")

    def extract_text(self, file_path: str, **kwargs) -> str:
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Fichier introuvable : {file_path}")
                return ""

            with open(file_path, "r", encoding=self.encoding) as f:
                content = f.read().strip()

            self.logger.info(f"Markdown extrait depuis {file_path} ({len(content)} caractères).")
            return content

        except UnicodeDecodeError:
            self.logger.warning(f"Problème d’encodage sur {file_path}, tentative en latin-1.")
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read().strip()
                return content
            except Exception as e:
                self.logger.exception(f"Erreur d’encodage sur {file_path} : {e}")
                return ""

        except Exception as e:
            self.logger.exception(f"Erreur lors de la lecture du fichier markdown : {e}")
            return ""