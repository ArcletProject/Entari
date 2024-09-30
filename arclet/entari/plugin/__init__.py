from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger
from tarina import init_spec

from .model import Plugin
from .model import PluginMetadata as PluginMetadata
from .model import RegisterNotInPluginError, _current_plugin
from .model import keeping as keeping
from .module import import_plugin
from .module import package as package
from .service import service

if TYPE_CHECKING:
    from ..event import Event


def dispatch(*events: type[Event], predicate: Callable[[Event], bool] | None = None):
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    return plugin.dispatch(*events, predicate=predicate)


def load_plugin(path: str, recursive_guard: set[str] | None = None) -> Plugin | None:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
        recursive_guard (set[str]): 递归保护
    """
    if recursive_guard is None:
        recursive_guard = set()
    if path in service._submoded:
        logger.error(f"plugin {path!r} is already defined as submodule of {service._submoded[path]!r}")
        return
    if path in service.plugins:
        return service.plugins[path]
    try:
        mod = import_plugin(path)
        if not mod:
            logger.error(f"cannot found plugin {path!r}")
            return
        logger.success(f"loaded plugin {path!r}")
        if mod.__name__ in service._unloaded:
            if mod.__name__ in service._referents and service._referents[mod.__name__]:
                referents = service._referents[mod.__name__].copy()
                service._referents[mod.__name__].clear()
                for referent in referents:
                    if referent in recursive_guard:
                        continue
                    if referent in service.plugins:
                        logger.debug(f"reloading {mod.__name__}'s referent {referent!r}")
                        dispose(referent)
                        if not load_plugin(referent):
                            service._referents[mod.__name__].add(referent)
                        else:
                            recursive_guard.add(referent)
            service._unloaded.discard(mod.__name__)
        return mod.__plugin__
    except RegisterNotInPluginError as e:
        logger.exception(f"{e.args[0]}", exc_info=e)
    except Exception as e:
        logger.exception(f"failed to load plugin {path!r} caused by {e!r}", exc_info=e)


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
        return False
    _plugin = service.plugins[plugin]
    _plugin.dispose()
    return True


@init_spec(PluginMetadata)
def metadata(data: PluginMetadata):
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    plugin._metadata = data  # type: ignore
