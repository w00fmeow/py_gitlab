import logging

logging.basicConfig(level=logging.DEBUG,
                    format='[ %(name)s ] - %(levelname)s : %(message)s')

logger = logging.getLogger("Gitlab")

file_handler = logging.FileHandler("/tmp/py_gitlab.log")
logger.addHandler(file_handler)
