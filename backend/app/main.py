from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import time
import uuid

from app.core.logging_config import setup_logging

setup_logging()

from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router

logger = logging.getLogger("app.main")
http_logger = logging.getLogger("app.http")


def get_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


allowed_origins = get_allowed_origins()

logger.info("Application démarrée | APP_ENV=%s", os.getenv("APP_ENV", "dev"))
logger.info("CORS origins autorisées | origins=%s", allowed_origins)

app = FastAPI(
    title="RAG Chat API",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(documents_router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()

    http_logger.info(
        "HTTP start | request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    http_logger.info(
        "HTTP end | request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
def root():
    return {"message": "RAG Chat API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}