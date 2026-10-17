from __future__ import annotations

import fnmatch
import inspect
import logging
import sys
import traceback
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, cast

from arclet.letoderea.exceptions import ExceptionHandler, Trace
from loguru import logger
from satori.parser import snake_case

from .utils import escape_tag

if TYPE_CHECKING:
    from loguru import Logger, Record


TRACE_NO = logger.level("TRACE").no
DEBUG_NO = logger.level("DEBUG").no


class LoggerManager:
    def __init__(self):
        self.loggers: dict[str, Logger] = {}
        self.fork("[core]")
        self.fork("[plugin]")
        self.fork("[message]")
        self.fork("[error]")
        self.log_level = "INFO"
        self.levelno = logger.level("INFO").no
        self.ignores = set()
        self.short_level = False

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

    @property
    def error(self):
        return self.loggers["[error]"]

    def wrapper(self, name: str, color: str = "blue"):
        name = escape_tag(name)
        if name.startswith("[") and name.endswith("]"):
            name1 = f"[{snake_case(name[1:-1])}]"
        else:
            name1 = snake_case(name)
        patched = logger.patch(lambda r: r.update(name=name1, extra=r["extra"] | {"entari_plugin_color": color}))
        patched = patched.bind(name=f"plugins.{name1}")
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
        self.levelno = logger.level(level).no if isinstance(level, str) else level


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
    if any(fnmatch.fnmatch(record["name"], pattern) for pattern in log.ignores):
        return False
    if record["name"].startswith("launart"):
        if log.levelno <= TRACE_NO:
            return record["level"].no >= logger.level("TRACE").no
        elif log.levelno <= DEBUG_NO:
            return record["level"].no >= logger.level("SUCCESS").no
        else:
            return record["level"].no > logger.level("SUCCESS").no
    return record["level"].no >= log.levelno


def _custom_format(record: Record):
    color = record["extra"].get("entari_plugin_color", "m")
    if record["name"].startswith("[") and record["name"].endswith("]"):  # type: ignore
        name = f"<{color}>{{name}}</{color}>"
    else:
        name = f"<{color}><u>{{name}}</u></{color}>"
    if log.levelno <= TRACE_NO:
        time = "<lk>{time:YYYY-MM-DD HH:mm:ss.SSS}</lk>"
    elif log.levelno <= DEBUG_NO:
        time = "<lk>{time:YYYY-MM-DD HH:mm:ss}</lk>"
    else:
        time = "<lk>{time:MM-DD HH:mm:ss}</lk>"
    level = "<lvl>{level:<7}</lvl> │"
    if log.short_level:
        level = "[<lvl>{level.name[0]}</lvl>]"
    res = f"{time} {level} {name} <lvl>{{message}}</lvl>\n"
    if record["exception"]:
        res += "{exception}\n"
    return res


logger.remove()
logger_id = logger.add(
    sys.stdout,
    level=0,
    diagnose=True,
    backtrace=False,
    colorize=True,
    filter=default_filter,
    format=_custom_format,
)
"""默认日志处理器 id"""


_HIDDEN_UPSTREAMS = {
    "satori": "satori",
    "launart": "launart",
    "uvicorn": "uvicorn",
    "starlette": "starlette",
    "graia.amnesia": "amnesia",
}


def add_hidden_upstream(prefix: str, name: str):
    """添加隐藏上游日志源

    Args:
        prefix (str): 日志源前缀
        name (str): 日志源名称
    """
    _HIDDEN_UPSTREAMS[prefix] = name


def _hidden_upsteam(record: Record):
    for prefix, name in _HIDDEN_UPSTREAMS.items():
        if record["name"].startswith(prefix):  # type: ignore
            record["name"] = name


logger.configure(patcher=_hidden_upsteam)


class _Sentinel(Enum):
    SENTINEL = "SENTINEL"


def _parse_value_tb(exc, value, tb) -> tuple[BaseException, TracebackType | None] | tuple[None, None]:
    if (value is _Sentinel.SENTINEL) != (tb is _Sentinel.SENTINEL):
        raise ValueError("Both or neither of value and tb must be given")
    if value is tb is _Sentinel.SENTINEL:
        if exc is not None:
            if isinstance(exc, BaseException):
                return exc, exc.__traceback__
            raise TypeError(f"Exception expected for value, {type(exc).__name__} found")
        else:
            return None, None
    return value, tb


_print_exception = traceback.print_exception


def loguru_print_exception(
    exc: type[BaseException] | BaseException | None,
    /,
    value: BaseException | None = _Sentinel.SENTINEL,  # type: ignore
    tb: TracebackType | None = _Sentinel.SENTINEL,  # type: ignore
    *args,
    **kwargs,
):
    colorize = kwargs.pop("colorize", True)
    value, tb = _parse_value_tb(exc, value, tb)
    if colorize:
        exc_type = type(value) if value is not None else Exception
        log.error.opt(exception=(exc_type, value, tb), colors=colorize).error("Exception:")
    elif isinstance(exc, BaseException):
        _print_exception(exc, **kwargs)
    else:
        _print_exception(exc, value, tb, *args, **kwargs)


def loguru_print_trace(te: Trace):
    summary = te.stack[0]
    true_frame = te.exc_traceback.tb_frame if te.exc_traceback else None

    class FakeFrame:
        f_code = type(
            "code", (), {"co_filename": summary.filename, "co_name": summary.name, "co_firstlineno": summary.lineno}
        )
        f_lineno = summary.lineno
        f_globals = {}
        f_locals = {}
        f_builtins = {}
        f_back = true_frame if true_frame and true_frame.f_code.co_filename != summary.filename else None

    class FakeTraceback:
        tb_frame = FakeFrame()
        tb_lineno = summary.lineno
        tb_next = te.exc_traceback

    log.error.opt(exception=(te.exc_type, te.exc_value, cast(TracebackType, FakeTraceback()))).error("Exception:")


def loguru_excepthook(cls: type[BaseException], val: BaseException, tb: TracebackType | None):
    """loguru 异常回调

    Args:
        cls (Type[Exception]): 异常类
        val (Exception): 异常的实际值
        tb (TracebackType): 回溯消息
    """
    log.error.opt(exception=(cls, val, tb)).error("Exception:")


traceback.print_exception = loguru_print_exception
ExceptionHandler.print_trace = loguru_print_trace
sys.excepthook = loguru_excepthook


def apply_log_save(
    log_dir: str | Path,
    rotation: str = "00:00",
    compression: str | None = "zip",
    colorize: bool = False,
):
    log_id = logger.add(
        f"{log_dir}/latest.log",
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


try:
    from loguru._better_exceptions import ExceptionFormatter
    from rich.console import Console
    from rich.traceback import Frame, Traceback

    csl = Console(stderr=False, force_terminal=True)

    def patch_format_exception(self, type_, value, tb, *, from_decorator=False):
        rich_tb = Traceback.from_exception(
            type_,
            value,
            tb,
            show_locals=True,
            width=csl.width,
            code_width=120 if csl.width > 120 else 88,
        )
        segments = [*csl.render(rich_tb)]
        yield csl._render_buffer(segments)

    def patch_print_trace(te: Trace):
        trace = Traceback.extract(te.exc_type, te.exc_value, te.exc_traceback, show_locals=True)
        summary = te.stack[0]
        trace.stacks[0].frames.insert(0, Frame(summary.filename, summary.lineno, summary.name, summary.line, locals={}))  # type: ignore
        rich_tb = Traceback(trace, width=csl.width, code_width=120 if csl.width > 120 else 88)
        segments = [*csl.render(rich_tb)]
        log.error.opt().error(f"Exception:\n{''.join(csl._render_buffer(segments))}")

    def enable_rich_except():
        ExceptionFormatter.format_exception = patch_format_exception
        ExceptionHandler.print_trace = patch_print_trace

except ImportError:

    def enable_rich_except():
        log.error.warning("无法启用 rich except，未安装 rich 库，请通过 `pip install rich` 安装。")


__all__ = ["log", "logger_id", "apply_log_save", "escape_tag", "enable_rich_except", "add_hidden_upstream"]
