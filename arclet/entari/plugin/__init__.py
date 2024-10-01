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
from .service import plugin_service

if TYPE_CHECKING:
    from ..event import Event


def dispatch(*events: type[Event], predicate: Callable[[Event], bool] | None = None):
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    return plugin.dispatch(*events, predicate=predicate)


def load_plugin(path: str, config: dict | None = None, recursive_guard: set[str] | None = None) -> Plugin | None:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
        config (dict): 模块配置
        recursive_guard (set[str]): 递归保护
    """
    if recursive_guard is None:
        recursive_guard = set()
    path = path.replace("::", "arclet.entari.plugins.")
    if path in plugin_service._submoded:
        logger.error(f"plugin {path!r} is already defined as submodule of {plugin_service._submoded[path]!r}")
        return
    if path in plugin_service.plugins:
        return plugin_service.plugins[path]
    try:
        mod = import_plugin(path, config=config)
        if not mod:
            logger.error(f"cannot found plugin {path!r}")
            return
        logger.success(f"loaded plugin {path!r}")
        if mod.__name__ in plugin_service._unloaded:
            if mod.__name__ in plugin_service._referents and plugin_service._referents[mod.__name__]:
                referents = plugin_service._referents[mod.__name__].copy()
                plugin_service._referents[mod.__name__].clear()
                for referent in referents:
                    if referent in recursive_guard:
                        continue
                    if referent in plugin_service.plugins:
                        logger.debug(f"reloading {mod.__name__}'s referent {referent!r}")
                        dispose(referent)
                        if not load_plugin(referent):
                            plugin_service._referents[mod.__name__].add(referent)
                        else:
                            recursive_guard.add(referent)
            plugin_service._unloaded.discard(mod.__name__)
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
    if plugin not in plugin_service.plugins:
        return False
    _plugin = plugin_service.plugins[plugin]
    _plugin.dispose()
    return True


@init_spec(PluginMetadata)
def metadata(data: PluginMetadata):
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    plugin._metadata = data  # type: ignore


def find_plugin(name: str) -> Plugin | None:
    if name in plugin_service.plugins:
        return plugin_service.plugins[name]
    if name in plugin_service._submoded:
        return plugin_service.plugins[plugin_service._submoded[name]]
    return None


def find_plugin_by_file(file: str) -> Plugin | None:
    path = Path(file).resolve()
    for plugin in plugin_service.plugins.values():
        if plugin.module.__file__ == str(path):
            return plugin
        if plugin.module.__file__ and Path(plugin.module.__file__).parent == path:
            return plugin
        for submod in plugin.submodules.values():
            if submod.__file__ == str(path):
                return plugin
            if submod.__file__ and Path(submod.__file__).parent == path:
                return plugin
        path1 = Path(path)
        while path1.parent != path1:
            if str(path1) == plugin.module.__file__:
                return plugin
            path1 = path1.parent
    return None
