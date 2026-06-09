import logging
import os
from logging.handlers import RotatingFileHandler


os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("mdp_sync")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

file_handler = RotatingFileHandler(
    "logs/sync.log",
    maxBytes=5_000_000,
    backupCount=3,
    encoding="utf-8"
)

file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)