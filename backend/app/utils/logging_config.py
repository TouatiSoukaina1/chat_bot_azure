import os
import logging

def setup_logger():
    LOG_DIR = os.path.join(os.getcwd(), "logs")
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Handlers
    fh_app = logging.FileHandler(os.path.join(LOG_DIR, "application.log"), encoding="utf-8")
    fh_app.setLevel(logging.INFO)
    fh_app.setFormatter(formatter)

    fh_error = logging.FileHandler(os.path.join(LOG_DIR, "errors.log"), encoding="utf-8")
    fh_error.setLevel(logging.ERROR)
    fh_error.setFormatter(formatter)

    fh_warning = logging.FileHandler(os.path.join(LOG_DIR, "warning.log"), encoding="utf-8")
    fh_warning.setLevel(logging.WARNING)
    fh_warning.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    # Ajout au logger principal
    logger.addHandler(fh_app)
    logger.addHandler(fh_error)
    logger.addHandler(fh_warning)
    logger.addHandler(ch)

    return logger
