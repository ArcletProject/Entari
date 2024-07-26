from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger

from .model import Plugin
from .model import PluginMetadata as PluginMetadata
from .model import _current_plugin
from .module import import_plugin
from .service import service

if TYPE_CHECKING:
    from ..event import Event


def dispatch(*events: type[Event], predicate: Callable[[Event], bool] | None = None):
    if not (plugin := _current_plugin.get()):
        raise LookupError("no plugin context found")
    return plugin.dispatch(*events, predicate=predicate)


def load_plugin(path: str) -> Plugin | None:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
    """
    if path in service.plugins:
        return service.plugins[path]
    try:
        mod = import_plugin(path)
        if not mod:
            logger.error(f"cannot found plugin {path!r}")
            return
        logger.success(f"loaded plugin {path!r}")
        return mod.__plugin__
    except Exception as e:
        logger.error(f"failed to load plugin {path!r} caused by {e!r}")


def load_plugins(dir_: str | PathLike | Path):
    path = dir_ if isinstance(dir_, Path) else Path(dir_)
    if path.is_dir():
        for p in path.iterdir():
            if p.suffix in (".py", "") and p.stem not in {"__init__", "__pycache__"}:
                load_plugin(".".join(p.parts[:-1:1]) + "." + p.stem)
    elif path.is_file():
        load_plugin(".".join(path.parts[:-1:1]) + "." + path.stem)


def dispose(plugin: str):
    if plugin not in service.plugins:
        return
    _plugin = service.plugins[plugin]
    _plugin.dispose()
