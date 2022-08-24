#!/usr/bin/env python3
import logging
from src.config import PROJECT_DIR

logging.basicConfig(level=logging.DEBUG,
                    format='[ %(name)s ] - %(levelname)s : %(message)s')

logger = logging.getLogger("Gitlab")

file_handler = logging.FileHandler(f"{PROJECT_DIR}/py_gitlab.log")
logger.addHandler(file_handler)
