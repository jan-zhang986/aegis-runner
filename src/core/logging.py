# -*- coding: utf-8 -*-
"""
Aegis Runner Core Logging Component
"""

import logging.config
import os
import sys
import colorlog
from logging.handlers import TimedRotatingFileHandler
from src.core.config import LOG_DIR


class Logger(object):

    level_relations = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    def __init__(self, app_name, log_level="INFO", file_path="logs"):
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(self.level_relations.get(log_level, logging.INFO))

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        file_handler = TimedRotatingFileHandler(
            os.path.join(str(LOG_DIR), f"{app_name}"), when='D', backupCount=7)
        file_handler.setLevel(log_level)

        self.log_colors_config = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        }
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            log_colors=self.log_colors_config
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)


LOGGER = Logger("aegis-runner")


def add_endpoint_logger(endpoint_name: str) -> Logger:
    return Logger(f"endpoint-{endpoint_name}")
