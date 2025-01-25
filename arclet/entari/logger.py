from __future__ import annotations

import inspect
import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger, Record


class LoggerManager:
    def __init__(self):
        self.loggers: dict[str, Logger] = {}
        self.fork("[core]")
        self.fork("[plugin]")
        self.fork("[message]")

    def fork(self, child_name: str):
        patched = logger.patch(lambda r: r.update(name=child_name))
        patched = patched.bind(name=child_name).opt(colors=True)
        self.loggers[child_name] = patched
        return patched

    @property
    def core(self):
        return self.loggers["[core]"]

    @property
    def plugin(self):
        return self.loggers["[plugin]"]

    @property
    def message(self):
        return self.loggers["[message]"]

    def wrapper(self, name: str, color: str = "blue"):
        patched = logger.patch(
            lambda r: r.update(name="entari", extra={"entari_plugin_name": name, "entari_plugin_color": color})
        )
        patched = patched.bind(name=f"plugins.{name}")
        self.loggers[f"plugin.{name}"] = patched
        return patched

    @staticmethod
    def set_level(level: str | int):
        if isinstance(level, str):
            level = level.upper()
        logging.basicConfig(
            handlers=[LoguruHandler()],
            level=level,
            format="%(asctime)s | %(name)s[%(levelname)s]: %(message)s",
        )
        logger.configure(extra={"entari_log_level": level}, patcher=_hidden_upsteam)


class LoguruHandler(logging.Handler):  # pragma: no cover
    """logging 与 loguru 之间的桥梁，将 logging 的日志转发到 loguru。"""

    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(
    handlers=[LoguruHandler()],
    level="INFO",
    format="%(asctime)s | %(name)s[%(levelname)s]: %(message)s",
)


def default_filter(record):
    if record["name"].startswith("launart"):
        return record["level"].no >= logger.level("SUCCESS").no
    log_level = record["extra"].get("entari_log_level", "INFO")
    levelno = logger.level(log_level).no if isinstance(log_level, str) else log_level
    return record["level"].no >= levelno


def _custom_format(record: Record):
    if "entari_plugin_name" in record["extra"]:
        plugin = (
            f" <{record['extra']['entari_plugin_color']}>"
            f"{record['extra']['entari_plugin_name']}"
            f"</{record['extra']['entari_plugin_color']}>"
        )
    else:
        plugin = ""
    return (
        f"<lk>{{time:YYYY-MM-DD HH:mm:ss}}</lk> <lvl>{{level}}</lvl> | <m><u>{{name}}</u></m>"
        f"{plugin} <lvl>{{message}}</lvl>\n"
    )


logger.remove()
logger_id = logger.add(
    sys.stdout,
    level=0,
    diagnose=True,
    backtrace=True,
    colorize=True,
    filter=default_filter,
    format=_custom_format,
)
"""默认日志处理器 id"""


def _hidden_upsteam(record: Record):
    if record["name"].startswith("satori"):  # type: ignore
        record["name"] = "satori"
    if record["name"].startswith("launart"):  # type: ignore
        record["name"] = "launart"


logger.configure(patcher=_hidden_upsteam)
log = LoggerManager()


__all__ = ["log"]
