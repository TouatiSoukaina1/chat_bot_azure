import time
import logging
from typing import Dict, Optional
from prometheus_client import Counter, Histogram

logger = logging.getLogger("app.metrics")

# ---- Compteurs globaux ----
chunks_processed = Counter("rag_chunks_total", "Nombre total de chunks traités", ["stage", "status"])
embedding_latency = Histogram("rag_embedding_latency_seconds", "Latence d'embedding (sec)", ["batch_size"])
indexing_latency = Histogram("rag_indexing_latency_seconds", "Latence d'indexation (sec)", ["batch_size"])
pipeline_duration = Histogram("rag_pipeline_duration_seconds", "Durée totale du pipeline", ["document"])

def record_chunk(stage: str, status: str) -> None:
    """Incrémente les compteurs de chunks selon leur statut."""
    try:
        chunks_processed.labels(stage=stage, status=status).inc()
    except Exception as e:
        logger.warning(f"Erreur metrics.record_chunk : {e}")

def record_latency(metric, value: float, batch_size: int):
    """Enregistre une latence sur un histogramme."""
    try:
        metric.labels(batch_size=batch_size).observe(value)
    except Exception as e:
        logger.warning(f"Erreur metrics.record_latency : {e}")

def record_pipeline_duration(document_id: Optional[str], duration: float):
    """Enregistre la durée totale du pipeline."""
    try:
        pipeline_duration.labels(document=document_id or "unknown").observe(duration)
    except Exception as e:
        logger.warning(f"Erreur metrics.record_pipeline_duration : {e}")
