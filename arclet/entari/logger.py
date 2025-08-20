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
        self.log_level = "INFO"
        self.ignores = set()

    def fork(self, child_name: str):
        patched = logger.patch(lambda r: r.update(name=child_name))
        patched = patched.bind(name=child_name)
        self.loggers[child_name] = patched
        return patched

    @property
    def core(self):
        return self.loggers["[core]"].opt(colors=True)

    @property
    def plugin(self):
        return self.loggers["[plugin]"].opt(colors=True)

    @property
    def message(self):
        return self.loggers["[message]"]

    def wrapper(self, name: str, color: str = "blue"):
        patched = logger.patch(
            lambda r: r.update(
                name="entari", extra=r["extra"] | {"entari_plugin_name": name, "entari_plugin_color": color}
            )
        )
        patched = patched.bind(name=f"plugins.{name}")
        self.loggers[name] = patched
        return patched

    def set_level(self, level: str | int):
        if isinstance(level, str):
            level = level.upper()
        logging.basicConfig(
            handlers=[LoguruHandler()],
            level="NOTSET" if level == "TRACE" else level,
            format="%(asctime)s | %(name)s[%(levelname)s]: %(message)s",
            force=True,
        )
        self.log_level = level


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
    force=True,
)

log = LoggerManager()


def default_filter(record):
    if record["name"] in log.ignores:
        return False
    levelno = logger.level(log.log_level).no if isinstance(log.log_level, str) else log.log_level
    if record["name"].startswith("launart"):
        if levelno <= logger.level("TRACE").no:
            return record["level"].no >= logger.level("TRACE").no
        elif levelno <= logger.level("DEBUG").no:
            return record["level"].no >= logger.level("SUCCESS").no
        else:
            return record["level"].no > logger.level("SUCCESS").no
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
    res = (
        f"<lk>{{time:YYYY-MM-DD HH:mm:ss}}</lk> <lvl>{{level:<7}}</lvl> | <m><u>{{name}}</u></m>"
        f"{plugin} <lvl>{{message}}</lvl>\n"
    )
    if record["exception"]:
        res += "{exception}\n"
    return res


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
    if record["name"].startswith("uvicorn"):  # type: ignore
        record["name"] = "uvicorn"
    if record["name"].startswith("starlette"):  # type: ignore
        record["name"] = "starlette"
    if record["name"].startswith("graia.amnesia"):  # type: ignore
        record["name"] = "graia.amnesia"


logger.configure(patcher=_hidden_upsteam)


def apply_log_save(
    rotation: str = "00:00",
    compression: str | None = "zip",
    colorize: bool = False,
):
    log_id = logger.add(
        "logs/latest.log",
        level=0,
        enqueue=False,
        rotation=rotation,
        compression=compression,
        colorize=colorize,
        diagnose=True,
        backtrace=True,
        filter=default_filter,
        format=_custom_format,
    )
    return lambda: logger.remove(log_id)


__all__ = ["log", "logger_id", "apply_log_save"]
