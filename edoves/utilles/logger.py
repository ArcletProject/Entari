import os
import sys

import loguru
import time


info_format = (
        '<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level: <8}</level> | '
        '<cyan>{name}</cyan> - <level>{message}</level>'
    )
debug_format = (
        '<green>{time:YYYY-MM-DD HH:mm:ss.SSSS}</green> | <level>{level: <9}</level> | '
        '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> '
    )


class Logger:
    logger: loguru.logger = loguru.logger

    def __init__(self, level='INFO'):
        log_format = debug_format if level == 'DEBUG' else info_format
        self.logger.remove()
        self.logger.add(
            os.path.join(
                os.getcwd(), 'logs', 'bot_running_log_' + time.strftime("%Y-%m-%d", time.localtime()) + '.log'
            ),
            format=log_format,
            level=level,
            enqueue=True,
            rotation="00:00",
            compression='zip',
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
            colorize=False,
        )
        self.logger.add(sys.stderr, level=level, format=log_format, backtrace=True, diagnose=True, colorize=True,)
        self.logger.info("--------------------------------------------------------")
