chat_bot_azure/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py              # Configuration centralisée
│   │   │   └── logging_config.py        # Configuration des logs
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── database.py              # Connexion DB
│   │   │   └── azure_clients.py         # Clients Azure (OpenAI, Search, Storage)
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── document.py              # Modèle Document
│   │   │   ├── chunk.py                 # Modèle Chunk
│   │   │   └── chat_history.py          # Modèle Historique Chat
│   │   │
│   │   ├── data_preparation/
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base_parser.py       # Classe abstraite
│   │   │   │   ├── image_parser.py      # Votre DoctrOCR
│   │   │   │   ├── pdf_parser.py
│   │   │   │   └── txt_parser.py
│   │   │   │
│   │   │   ├── processors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── text_cleaner.py      # Nettoyage de texte
│   │   │   │   ├── chunker.py           # Découpage en chunks
│   │   │   │   └── embedder.py          # Génération embeddings
│   │   │   │
│   │   │   ├── pipelines/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── extraction_pipeline.py
│   │   │   │   ├── chunking_pipeline.py
│   │   │   │   └── ingestion_pipeline.py
│   │   │   │
│   │   │   └── trackers/
│   │   │       ├── __init__.py
│   │   │       ├── document_tracker.py  # Tracking des documents
│   │   │       └── processing_status.py # États de traitement
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py      # Service métier documents
│   │   │   ├── chat_service.py          # Service métier chat RAG
│   │   │   ├── search_service.py        # Service recherche vectorielle
│   │   │   └── history_service.py       # Service historique chat
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                  # FastAPI app
│   │   │   ├── dependencies.py          # Dépendances FastAPI
│   │   │   │
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── documents.py         # Routes upload/documents
│   │   │   │   ├── chat.py              # Routes chat
│   │   │   │   └── health.py            # Health check
│   │   │   │
│   │   │   └── schemas/
│   │   │       ├── __init__.py
│   │   │       ├── document.py          # Schémas Pydantic
│   │   │       ├── chat.py
│   │   │       └── response.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── file_handler.py          # Gestion fichiers
│   │       ├── hash_utils.py            # Calcul hash
│   │       └── validators.py            # Validations
│   │
│   ├── data/
│   │   ├── raw/                         # Documents bruts
│   │   ├── extracted/                   # Textes extraits
│   │   ├── chunks/                      # Chunks JSON
│   │   └── database/
│   │       └── tracker.db               # SQLite
│   │
│   ├── logs/                            # Logs applicatifs
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                  # Fixtures pytest
│   │   │
│   │   ├── unit/
│   │   │   ├── __init__.py
│   │   │   ├── test_parsers.py
│   │   │   ├── test_chunker.py
│   │   │   ├── test_embedder.py
│   │   │   └── test_services.py
│   │   │
│   │   ├── integration/
│   │   │   ├── __init__.py
│   │   │   ├── test_pipelines.py
│   │   │   └── test_api.py
│   │   │
│   │   └── fixtures/
│   │       ├── sample.pdf
│   │       ├── sample.jpg
│   │       └── sample.txt
│   │
│   ├── scripts/
│   │   ├── run_extraction.py
│   │   ├── run_chunking.py
│   │   ├── run_ingestion.py
│   │   ├── run_full_pipeline.py
│   │   └── cleanup_database.py
│   │
│   ├── requirements.txt
│   ├── requirements-dev.txt             # Dépendances dev/test
│   ├── .env.example
│   └── README.md
│
├── frontend/
│   └── (votre interface React)
│
├── infra/
│   ├── bicep/
│   │   ├── main.bicep
│   │   └── modules/
│   └── terraform/
│
└── docker-compose.yml