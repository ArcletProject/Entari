from __future__ import annotations

import inspect
from os import PathLike
from pathlib import Path
from typing import Any, Callable, TypeVar, overload

from arclet.letoderea import es
from tarina import init_spec

from ..config import EntariConfig, config_model_validate
from ..event.plugin import PluginLoadedFailed, PluginLoadedSuccess, PluginUnloaded
from ..logger import log
from .model import PluginMetadata as PluginMetadata
from .model import RegisterNotInPluginError
from .model import RootlessPlugin as RootlessPlugin
from .model import StaticPluginDispatchError, _current_plugin
from .model import TE, TS, Plugin
from .model import keeping as keeping
from .module import import_plugin
from .module import package as package
from .module import requires as requires
from .service import plugin_service


def get_plugin(depth: int = 0) -> Plugin:
    if plugin := _current_plugin.get(None):
        return plugin
    current_frame = inspect.currentframe()
    if current_frame is None:
        raise ValueError("Depth out of range")
    frame = current_frame
    d = depth + 1
    while d > 0:
        frame = frame.f_back
        if frame is None:
            raise ValueError("Depth out of range")
        d -= 1
    locals_ = frame.f_locals
    if "__plugin__" in locals_:
        return locals_["__plugin__"]
    globals_ = frame.f_globals
    if "__plugin__" in globals_:
        return globals_["__plugin__"]
    raise LookupError("no plugin context found")


def dispatch(event: type[TE], name: str | None = None):
    return get_plugin(1).dispatch(event, name=name)


def load_plugin(
    path: str, config: dict | None = None, recursive_guard: set[str] | None = None, prelude: bool = False
) -> Plugin | None:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
        config (dict): 模块配置
        recursive_guard (set[str]): 递归保护
        prelude (bool): 是否为前置插件
    """
    if config is None:
        config = EntariConfig.instance.plugin.get(path)
    conf = (config or {}).copy()
    if prelude:
        conf["$static"] = True
    if recursive_guard is None:
        recursive_guard = set()
    path = path.replace("::", "arclet.entari.builtins.")
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if path in plugin_service._apply:
        return plugin_service._apply[path](conf)
    if plug := find_plugin(path):
        return plug
    try:
        if pref := conf.pop("$prefix", None):
            path = f"{pref if isinstance(pref, str) else 'entari_plugin'}_{path}"
        mod = import_plugin(path, config=conf)
        if not pref and not mod:
            path1 = f"entari_plugin_{path}"
            mod = import_plugin(path1, config=conf)
        if not mod:
            log.plugin.error(f"cannot found plugin <blue>{path!r}</blue>")
            es.publish(PluginLoadedFailed(path))
            return
        if mod.__name__ in plugin_service._unloaded:
            if mod.__name__ in plugin_service._referents and plugin_service._referents[mod.__name__]:
                referents = plugin_service._referents[mod.__name__].copy()
                plugin_service._referents[mod.__name__].clear()
                for referent in referents:
                    if referent in recursive_guard:
                        continue
                    if referent in plugin_service.plugins:
                        log.plugin.debug(f"reloading <y>{mod.__name__}</y>'s referent <y>{referent!r}</y>")
                        unload_plugin(referent)
                        if not load_plugin(referent):
                            plugin_service._referents[mod.__name__].add(referent)
                        else:
                            recursive_guard.add(referent)
            plugin_service._unloaded.discard(mod.__name__)
        es.publish(PluginLoadedSuccess(mod.__name__))
        return mod.__plugin__
    except (ImportError, RegisterNotInPluginError, StaticPluginDispatchError) as e:
        log.plugin.error(f"failed to load plugin <blue>{path!r}</blue>: {e.args[0]}")
        es.publish(PluginLoadedFailed(path, e))
    except Exception as e:
        log.plugin.exception(f"failed to load plugin <blue>{path!r}</blue> caused by {e!r}", exc_info=e)
        es.publish(PluginLoadedFailed(path, e))


def load_plugins(dir_: str | PathLike | Path):
    path = dir_ if isinstance(dir_, Path) else Path(dir_)
    if not path.is_dir():
        raise NotADirectoryError(f"{path} is not a directory")
    for p in path.iterdir():
        if p.suffix in (".py", "") and p.stem not in {"__init__", "__pycache__"}:
            load_plugin(".".join(p.parts[:-1:1]) + "." + p.stem)


@init_spec(PluginMetadata)
def metadata(data: PluginMetadata):
    get_plugin(1)._metadata = data  # type: ignore


_C = TypeVar("_C")


@overload
def plugin_config() -> dict[str, Any]: ...


@overload
def plugin_config(model_type: type[_C]) -> _C: ...


def plugin_config(model_type: type[_C] | None = None):
    """获取当前插件的配置"""
    plugin = get_plugin(1)
    if model_type:
        return config_model_validate(model_type, plugin.config)
    return plugin.config


get_config = plugin_config


def declare_static():
    """声明当前插件为静态插件"""
    plugin = get_plugin(1)
    plugin.is_static = True
    if plugin._scope.subscribers:
        raise StaticPluginDispatchError("static plugin cannot dispatch events")


def add_service(serv: TS | type[TS]) -> TS:
    return get_plugin(1).service(serv)


def collect_disposes(*disposes: Callable[[], None]):
    """收集副作用回收函数"""
    return get_plugin(1).collect(*disposes)


def restore():
    """回收该插件收集的所有副作用"""
    return get_plugin(1).restore()


def find_plugin(name: str) -> Plugin | None:
    if name in plugin_service.plugins:
        return plugin_service.plugins[name]
    if f"entari_plugin_{name}" in plugin_service.plugins:
        return plugin_service.plugins[f"entari_plugin_{name}"]


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


def unload_plugin(plugin: str):
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
    if not (_plugin := find_plugin(plugin)):
        return False
    es.publish(PluginUnloaded(_plugin.id))
    _plugin.dispose()
    return True


listen = es.on
