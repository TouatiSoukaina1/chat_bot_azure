import re
import logging
from typing import List, Dict, Any, Optional


class Chunker:
    """
    Chunker Markdown-first:
    - split par headings Markdown (#, ##, ### ...)
    - sous-chunking par paragraphes (chunk_size / overlap)
    - conserve section_title dans le dict de sortie

    Retour attendu par ton pipeline:
      [{"id": 0, "text": "...", "section_title": "Symptoms"}, ...]
    """

    HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")

    def __init__(
        self,
        chunk_size: int = 1500,
        overlap: int = 150,
        include_section_prefix: bool = True,  # ajoute [SECTION] Symptoms en tête du chunk
        logger: Optional[logging.Logger] = None,
    ):
        self.chunk_size = int(chunk_size)
        self.overlap = int(overlap)
        self.include_section_prefix = include_section_prefix
        self.logger = logger or logging.getLogger("app.Chunker")

    def chunk_text(self, text: str, doc_title: Optional[str] = None) -> List[Dict[str, Any]]:
        if not isinstance(text, str) or not text.strip():
            self.logger.warning("Texte vide/invalide.")
            return []

        text = self._normalize(text)
        sections = self._split_markdown_sections(text)

        # fallback si pas de headings
        if not sections:
            sections = [("Body", text)]

        chunks: List[Dict[str, Any]] = []
        chunk_id = 0

        for section_title, section_body in sections:
            section_body = section_body.strip()
            if not section_body:
                continue

            section_chunks = self._chunk_section(
                section_body=section_body,
                section_title=section_title,
                doc_title=doc_title,
                start_id=chunk_id,
            )
            chunks.extend(section_chunks)
            if section_chunks:
                chunk_id = section_chunks[-1]["id"] + 1

        return chunks

    # -------------------- Markdown split --------------------

    def _split_markdown_sections(self, text: str) -> List[tuple]:
        """
        Split sur lignes commençant par # / ## / ### ...
        On retire la ligne heading du contenu, et on stocke le titre comme section_title.
        """
        lines = text.split("\n")

        sections: List[tuple] = []
        current_title: Optional[str] = None
        buf: List[str] = []

        def flush():
            nonlocal current_title, buf
            if current_title is not None:
                body = "\n".join(buf).strip()
                sections.append((current_title, body))
            buf = []

        for raw in lines:
            line = raw.strip()
            m = self.HEADING_RE.match(line)
            if m:
                # nouvelle section
                flush()
                current_title = (m.group(2) or "").strip()
                if not current_title:
                    current_title = "Section"
                continue
            buf.append(raw)

        # dernier flush
        if current_title is not None:
            flush()

        # Si le doc commence sans #, on met ça dans "Intro"
        # (buf au début aura été accumulé dans sections vide si current_title None)
        # Pour gérer ça proprement:
        if not sections:
            return []

        # Gérer un "préambule" avant le premier heading (si besoin)
        # Ici on ne l'a pas, car flush() n'ajoute que si current_title != None.
        # Donc si tu veux garder l'intro avant le 1er "#", tu peux la mettre toi-même en "# Overview".

        # Filtre sections vides
        return [(t, b) for (t, b) in sections if b and b.strip()]

    # -------------------- Sous-chunking --------------------

    def _chunk_section(
        self,
        section_body: str,
        section_title: str,
        doc_title: Optional[str],
        start_id: int,
    ) -> List[Dict[str, Any]]:
        paras = self._split_paragraphs(section_body)

        def prefix() -> str:
            if not self.include_section_prefix:
                return ""
            dt = (doc_title or "").strip()
            st = (section_title or "Section").strip()
            if dt:
                return f"[DOC] {dt}\n[SECTION] {st}\n\n"
            return f"[SECTION] {st}\n\n"

        pre = prefix()

        chunks: List[Dict[str, Any]] = []
        current: List[str] = []
        current_len = 0
        cid = start_id

        def finalize():
            nonlocal current, current_len, cid
            if not current:
                return

            body = "\n\n".join(current).strip()
            out = (pre + body).strip()
            if out:
                chunks.append({
                    "id": cid,
                    "text": out,
                    "section_title": section_title,
                    "doc_title": doc_title,
                })
                cid += 1

            # overlap en chars: on garde les derniers paragraphes
            carry: List[str] = []
            carry_len = 0
            for p in reversed(current):
                if carry_len + len(p) > self.overlap:
                    break
                carry.insert(0, p)
                carry_len += len(p)

            current = carry
            current_len = sum(len(p) for p in current)

        for p in paras:
            p = p.strip()
            if not p:
                continue

            # paragraphe énorme -> split en phrases simples
            if len(p) > self.chunk_size:
                for sp in self._split_big_paragraph(p):
                    sp = sp.strip()
                    if not sp:
                        continue
                    if current and current_len + len(sp) + 2 > self.chunk_size:
                        finalize()
                    current.append(sp)
                    current_len += len(sp) + 2
                continue

            if current and current_len + len(p) + 2 > self.chunk_size:
                finalize()

            current.append(p)
            current_len += len(p) + 2

        finalize()
        return chunks

    # -------------------- Helpers --------------------

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _split_paragraphs(text: str) -> List[str]:
        parts = re.split(r"\n\s*\n", text)
        return [p.strip() for p in parts if p and p.strip()]

    @staticmethod
    def _split_big_paragraph(p: str) -> List[str]:
        # split après ponctuation forte (sans NLP)
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", p.strip())
        if len(sents) <= 1:
            sents = re.split(r"(?<=[;:])\s+", p.strip())
        return [s.strip() for s in sents if s and s.strip()]
