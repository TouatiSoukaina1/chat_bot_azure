import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logging(
    level: str | None = None,
    log_dir: str | None = None,
    app_name: str = "app",
) -> None:
    """
    Logging "prod-friendly":
    - console + fichier
    - rotation quotidienne (garde N fichiers)
    - format lisible
    """
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_dir = log_dir or os.getenv("LOG_DIR", "logs")

    os.makedirs(log_dir, exist_ok=True)
    logfile = os.path.join(log_dir, f"{app_name}.log")

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # ⚠️ Important: éviter doublons si setup_logging est appelé plusieurs fois
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(fmt)

    # Fichier avec rotation quotidienne
    fh = TimedRotatingFileHandler(
        logfile,
        when="D",           # daily
        interval=1,
        backupCount=int(os.getenv("LOG_BACKUP_DAYS", "14")),  # garde 14 jours
        encoding="utf-8",
        utc=True,
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)

    # Réduire le bruit des SDK Azure (optionnel)
    logging.getLogger("azure").setLevel(os.getenv("AZURE_LOG_LEVEL", "WARNING").upper())
    logging.getLogger("urllib3").setLevel("WARNING")

    logging.getLogger(app_name).info("✅ Logging initialisé (level=%s, file=%s)", level, logfile)
