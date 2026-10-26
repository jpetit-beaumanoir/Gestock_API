import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from gestock_server.config import LOG_PATH

# Ruta del log definida en gestock.env (LOG_PATH). Puede ser relativa o absoluta,
# p. ej. LOG_PATH = '/home/aiq/data/gestock/logs/gestock.log'
LOG_FILE = Path(LOG_PATH)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def setup_logging():
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)