from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from tarina import init_spec

from ..config import EntariConfig
from ..logger import log
from .model import Plugin
from .model import PluginMetadata as PluginMetadata
from .model import RegisterNotInPluginError
from .model import RootlessPlugin as RootlessPlugin
from .model import _current_plugin
from .model import keeping as keeping
from .module import import_plugin
from .module import package as package
from .module import requires as requires
from .service import plugin_service

if TYPE_CHECKING:
    from ..event.base import BasedEvent


def dispatch(*events: type[BasedEvent], predicate: Callable[[BasedEvent], bool] | None = None, name: str | None = None):
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    return plugin.dispatch(*events, predicate=predicate, name=name)


def load_plugin(path: str, config: dict | None = None, recursive_guard: set[str] | None = None) -> Plugin | None:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
        config (dict): 模块配置
        recursive_guard (set[str]): 递归保护
    """
    if config is None:
        _config = EntariConfig.instance.plugin.get(path)
        if isinstance(_config, dict):
            config = _config.copy()
        elif _config is False:
            return
    if recursive_guard is None:
        recursive_guard = set()
    path = path.replace("::", "arclet.entari.builtins.")
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if path in plugin_service.plugins:
        return plugin_service.plugins[path]
    if path in plugin_service._apply:
        return plugin_service._apply[path](config or {})
    try:
        mod = import_plugin(path, config=config)
        if not mod:
            log.plugin.opt(colors=True).error(f"cannot found plugin <blue>{path!r}</blue>")
            return
        log.plugin.opt(colors=True).success(f"loaded plugin <blue>{path!r}</blue>")
        if mod.__name__ in plugin_service._unloaded:
            if mod.__name__ in plugin_service._referents and plugin_service._referents[mod.__name__]:
                referents = plugin_service._referents[mod.__name__].copy()
                plugin_service._referents[mod.__name__].clear()
                for referent in referents:
                    if referent in recursive_guard:
                        continue
                    if referent in plugin_service.plugins:
                        log.plugin.opt(colors=True).debug(
                            f"reloading <y>{mod.__name__}</y>'s referent <y>{referent!r}</y>"
                        )
                        dispose(referent)
                        if not load_plugin(referent):
                            plugin_service._referents[mod.__name__].add(referent)
                        else:
                            recursive_guard.add(referent)
            plugin_service._unloaded.discard(mod.__name__)
        return mod.__plugin__
    except RegisterNotInPluginError as e:
        log.plugin.opt(colors=True).error(f"{e.args[0]}")
    except Exception as e:
        log.plugin.opt(colors=True).exception(
            f"failed to load plugin <blue>{path!r}</blue> caused by {e!r}", exc_info=e
        )


def load_plugins(dir_: str | PathLike | Path):
    path = dir_ if isinstance(dir_, Path) else Path(dir_)
    if path.is_dir():
        for p in path.iterdir():
            if p.suffix in (".py", "") and p.stem not in {"__init__", "__pycache__"}:
                load_plugin(".".join(p.parts[:-1:1]) + "." + p.stem)
    elif path.is_file():
        load_plugin(".".join(path.parts[:-1:1]) + "." + path.stem)


def dispose(plugin: str):
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
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


def plugin_config() -> dict[str, Any]:
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    return plugin.config


def find_plugin(name: str) -> Plugin | None:
    return plugin_service.plugins.get(name)


def find_plugin_by_file(file: str) -> Plugin | None:
    path = Path(file).resolve()
    for plugin in plugin_service.plugins.values():
        if plugin.module.__file__ == str(path):
            return plugin
        if plugin.module.__file__ and Path(plugin.module.__file__).parent == path:
            return plugin
        path1 = Path(path)
        while path1.parent != path1:
            if str(path1) == plugin.module.__file__:
                return plugin
            path1 = path1.parent
    return None
