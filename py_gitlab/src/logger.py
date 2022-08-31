#!/usr/bin/env python3
import logging
from logging.handlers import TimedRotatingFileHandler
from src.config import LOGS_DIR

logging.basicConfig(level=logging.DEBUG,
                    format='[ %(name)s ] - %(levelname)s : %(message)s')

logger = logging.getLogger("Gitlab")

file_handler = TimedRotatingFileHandler(
    f"{LOGS_DIR}/py_gitlab.log", when="midnight", interval=1)

file_handler.suffix = "%Y%m%d"

logger.addHandler(file_handler)
