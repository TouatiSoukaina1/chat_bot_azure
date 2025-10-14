from app.core.database import DocumentRepository    
from app.data_preparation.processors import TextChunker
import logging

def run_chunking_pipeline():
    """
    Pipeline pour découper les textes des documents en chunks et les stocker dans la base de données.
    """
    repo = DocumentRepository()
    chunker = TextChunker(chunk_size=500, overlap=50)

    docs = repo.get_documents(status="parsed")
    logger = logging.getLogger("app.ChunkingPipeline")

    logger.info(f"Nombre de documents à découper : {len(docs)}")
    for path, text_content in docs:
        if not text_content:
            logger.warning(f"Document sans contenu textuel : {path}")
            continue

        chunks = chunker.chunk_text(text_content)
        if not chunks:
            logger.warning(f"Aucun chunk généré pour le document : {path}")
            continue

        # Stockage des chunks dans la base de données
        for chunk in chunks:
            chunk_id = f"{path}_chunk_{chunk['id']}"
            repo.add_chunk(chunk_id, path, chunk['text'])

        repo.update_status(path, "ingested")
        logger.info(f"Document découpé et stocké : {path} en {len(chunks)} chunks")