from typing import Any
import logging
import sys

class LineOALogger:
    def __init__(self, name: str = "LINEOALib", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(tag)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.propagate = False

    def login(self, msg: Any) -> None:
        self.logger.info(msg, extra={"tag": "LOGIN"})

    def info(self, msg: Any) -> None:
        self.logger.info(msg, extra={"tag": "INFO"})

    def error(self, msg: Any) -> None:
        self.logger.error(msg, extra={"tag": "ERROR"})

    def exception(self, msg: Any) -> None:
        self.logger.exception(msg, extra={"tag": "ERROR"})

lineoa_logger = LineOALogger()
logger = lineoa_logger.logger
