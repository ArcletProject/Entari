import os
import sys
import traceback
from asyncio import AbstractEventLoop

import loguru


def loguru_excepthook(cls, val, tb, *_, **__):
    """loguru 异常回调

    Args:
        cls (Type[Exception]): 异常类
        val (Exception): 异常的实际值
        tb (TracebackType): 回溯消息
    """
    loguru.logger.opt(exception=(cls, val, tb)).error("Exception:")


def loguru_async_handler(_, ctx: dict):
    """loguru 异步异常回调

    Args:
        _ (AbstractEventLoop): 异常发生的事件循环
        ctx (dict): 异常上下文
    """
    if "exception" in ctx:
        loguru.logger.opt(exception=ctx["exception"]).error("Exception:")
    else:
        loguru.logger.error(f"Exception: {ctx}")


def replace_traceback(loop: AbstractEventLoop = None):
    """使用 loguru 模块替换默认的 traceback.print_exception 与 sys.excepthook"""
    traceback.print_exception = loguru_excepthook
    sys.excepthook = loguru_excepthook
    if loop:
        loop.set_exception_handler(loguru_async_handler)


info_format = (
    '<green>{time:YYYY-MM-DD HH:mm:ss.S}</green> | <level>{level: <8}</level> | '
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
                os.getcwd(), 'logs', 'edoves_latest.log'
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
        self.logger.add(sys.stderr, level=level, format=log_format, backtrace=True, diagnose=True, colorize=True, )
