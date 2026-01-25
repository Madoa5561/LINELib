from typing import Any
import logging
import sys

class LineOALogger:
    def __init__(self, name: str = "LINEOALib", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(tag)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        self.logger.handlers = []
        self.logger.addHandler(handler)

    def login(self, msg: Any) -> None:
        self.logger.info(msg, extra={"tag": "LOGIN"})

    def info(self, msg: Any) -> None:
        self.logger.info(msg, extra={"tag": "INFO"})

    def error(self, msg: Any) -> None:
        self.logger.error(msg, extra={"tag": "ERROR"})

logger = LineOALogger().logger
lineoa_logger = LineOALogger()
