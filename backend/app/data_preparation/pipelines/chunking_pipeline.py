from app.core.database import DocumentRepository
from app.data_preparation.processors.chunker import TextChunker
import logging

def run_chunking_pipeline():
    """
        Pipeline pour découper les textes des documents en chunks et les stocker dans CosmosDB.
    """
    logger = logging.getLogger("app.ChunkingPipeline")

    # Connexion à la base CosmosDB
    repo = DocumentRepository()
    chunker = TextChunker(chunk_size=500, overlap=50)

    # Récupérer les documents extraits mais pas encore chunkés
    docs = repo.get_documents_by_status("parsed")

    if not docs:
        logger.warning("Aucun document à découper. Fin du pipeline.")
        return

    for doc in docs:
        doc_id = doc.get("id")
        path = doc.get("path")
        text_content = doc.get("text_content")
        file_type = doc.get("file_type", "txt")

        if not text_content:
            logger.warning(f"Document vide ignoré : {path}")
            continue

        chunks = chunker.chunk_text(text_content)
        if not chunks:
            logger.warning(f"Aucun chunk généré pour : {path}")
            continue

        # Enregistrer les chunks dans la abse de données
        for chunk in chunks:
            chunk_doc = {
                "id": f"{doc_id}_chunk_{chunk['id']}",
                "document_id": doc_id,
                "text": chunk["text"],
                "order": chunk["id"],
                "status": "chunked",
                "type": file_type,
                "source_path": path
            }
            #Insertion chunk dans la base de données (chunks)
            repo.insert_chunk(chunk_doc)

        #Mettre à jour le statut du document
        repo.update_document_status(document_id=doc_id, new_status="chunked", partition_key=file_type)

        logger.info(f"✅ Document découpé et stocké : {path} → {len(chunks)} chunks.")

    logger.info("Chunking pipeline terminé avec succès !")