from __future__ import annotations

import inspect
import itertools
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeVar, overload

from arclet.letoderea import Subscriber, on, publish
from tarina import init_spec
from tarina.tools import nest_obj_update

from ..config import EntariConfig, config_model_keys, config_model_validate
from ..event.config import ConfigReload
from ..event.lifespan import Ready
from ..event.plugin import PluginLoadedFailed, PluginUnloaded
from ..logger import log
from .model import PluginMetadata as PluginMetadata
from .model import RootlessPlugin as RootlessPlugin
from .model import StaticPluginDispatchError, _current_plugin
from .model import TE, TS, Plugin
from .model import keeping as keeping
from .module import import_plugin
from .module import package as package
from .module import requires as requires
from .service import plugin_service


@overload
def get_plugin(depth: int = 0) -> Plugin: ...


@overload
def get_plugin(depth: int = 0, *, optional: Literal[True]) -> Plugin | None: ...


def get_plugin(depth: int = 0, *, optional: bool = False) -> Plugin | None:
    """获取当前插件上下文

    Args:
        depth (int, optional): 获取的深度，默认为0，表示当前插件上下文. Defaults to 0.
        optional (bool, optional): 是否允许返回None，默认为False. Defaults to False.
    Raises:
        ValueError: 如果深度超出范围
        LookupError: 如果没有找到插件上下文
    Returns:
        Plugin | None: 当前插件上下文，如果没有找到且optional为True则返回None
    """
    if plugin := _current_plugin.get(None):
        return plugin
    current_frame = inspect.currentframe()
    if current_frame is None:
        if optional:
            return None
        raise ValueError("Depth out of range")
    frame = current_frame
    d = depth + 1
    while d > 0:
        frame = frame.f_back
        if frame is None:
            if optional:
                return None
            raise ValueError("Depth out of range")
        d -= 1
    locals_ = frame.f_locals
    if "__plugin__" in locals_:
        return locals_["__plugin__"]
    globals_ = frame.f_globals
    if "__plugin__" in globals_:
        return globals_["__plugin__"]
    if optional:
        return None
    raise LookupError("no plugin context found")


def get_plugins():
    return list(plugin_service.plugins.values())


def get_plugin_subscribers(plug: Plugin | str | None = None) -> list[Subscriber]:
    """获取指定插件的所有订阅者"""
    if isinstance(plug, Plugin):
        plg = plug
    elif plug in plugin_service.plugins:
        plg = plugin_service.plugins[plug]
    else:
        plg = get_plugin(1)
    return [s[0] for s in plg._scope.subscribers.values()]


def get_all_subscribers():
    """获取所有插件的所有订阅者"""
    return list(itertools.chain.from_iterable(get_plugin_subscribers(plug) for plug in plugin_service.plugins.values()))


def dispatch(event: type[TE], name: str | None = None):
    """对当前插件创建一个事件分发"""
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
        config = EntariConfig.instance.plugin.get(path, {})
    config["$path"] = path
    if prelude:
        config["$static"] = True
    if recursive_guard is None:
        recursive_guard = set()
    path = path.replace("::", "arclet.entari.builtins.")
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if path in plugin_service._apply:
        log.plugin.trace(f"loaded rootless plugin <y>{path!r}</y>")
        return plugin_service._apply[path][0](config)
    if plug := find_plugin(path):
        plugin_service._direct_plugins.add(plug.id)
        return plug
    try:
        if pref := config.get("$prefix"):
            path = f"{pref if isinstance(pref, str) else 'entari_plugin_'}{path}"
        mod = import_plugin(path, config=config)
        if not pref and not mod and not path.count("."):
            path1 = f"entari_plugin_{path}"
            mod = import_plugin(path1, config=config)
        if not mod:
            log.plugin.error(f"cannot found plugin <blue>{path!r}</blue>")
            publish(PluginLoadedFailed(path))
            return
        plugin_service._direct_plugins.add(mod.__name__)
        if mod.__name__ in plugin_service.referents and plugin_service.referents[mod.__name__]:
            referents = plugin_service.referents[mod.__name__].copy()
            plugin_service.referents[mod.__name__].clear()
            for referent in referents:
                if referent in recursive_guard:
                    continue
                if referent in plugin_service.plugins:
                    log.plugin.debug(f"reloading <y>{mod.__name__}</y>'s referent <y>{referent!r}</y>")
                    unload_plugin(referent)
                if not (plug := load_plugin(referent)):
                    plugin_service.referents[mod.__name__].add(referent)
                else:
                    publish(Ready(), plug._scope)
                    recursive_guard.add(referent)

        return mod.__plugin__
    except Exception:
        return


def load_plugins(dir_: str | PathLike | Path):
    """加载指定目录下的所有插件"""
    path = dir_ if isinstance(dir_, Path) else Path(dir_)
    if not path.is_dir():
        raise NotADirectoryError(f"{path} is not a directory")
    for p in path.iterdir():
        if p.suffix in (".py", "") and p.stem not in {"__init__", "__pycache__"}:
            load_plugin(".".join(p.parts[:-1:1]) + "." + p.stem)


if TYPE_CHECKING:

    @init_spec(PluginMetadata)
    def metadata(data: PluginMetadata) -> None:
        """声明当前插件的元数据"""

else:

    def metadata(*args, **kwargs):
        """声明当前插件的元数据"""
        get_plugin(1).metadata = PluginMetadata(*args, **kwargs)  # type: ignore


_C = TypeVar("_C")


@overload
def plugin_config() -> dict[str, Any]: ...


@overload
def plugin_config(model_type: type[_C], bind: bool = False) -> _C: ...


def plugin_config(model_type: type[_C] | None = None, bind: bool = False):
    """获取当前插件的配置

    Args:
        model_type (type[_C], optional): 配置模型类型. Defaults to None.
        bind (bool, optional): 是否将配置模型与配置绑定，绑定后配置模型的修改会更新配置文件,
            而配置文件的修改则直接作用在配置模型上，不再重载整个插件. Defaults to False.
    """
    plugin = get_plugin(1)
    if model_type:
        obj = config_model_validate(model_type, plugin.config)
        if bind:
            plugin_key = plugin._config_key

            def _reload(event: ConfigReload):
                if event.scope != "plugin":
                    return
                if event.key != plugin_key:
                    return
                new = config_model_validate(model_type, event.value)
                nest_obj_update(obj, new, config_model_keys(new))
                return True

            sub = plugin._scope.register(_reload, event=ConfigReload)
            proxy = EntariConfig.instance.bind(plugin_key, obj)
            plugin.collect(lambda: delattr(proxy, "_Proxy__origin"), sub.dispose)
            return proxy
        return obj
    return plugin.config


get_config = plugin_config


def declare_static():
    """声明当前插件为静态插件"""
    plugin = get_plugin(1)
    plugin.is_static = True
    if plugin._scope.subscribers:
        raise StaticPluginDispatchError("static plugin cannot dispatch events")


def add_service(serv: TS | type[TS]) -> TS:
    """添加一个服务到当前插件"""
    return get_plugin(1).service(serv)


def collect_disposes(*disposes: Callable[[], None]):
    """收集副作用回收函数"""
    return get_plugin(1).collect(*disposes)


def restore():
    """回收该插件收集的所有副作用"""
    return get_plugin(1).restore()


def find_plugin(name: str) -> Plugin | None:
    """根据插件名称查找插件"""
    if name in plugin_service.plugins:
        return plugin_service.plugins[name]
    if not name.count(".") and f"entari_plugin_{name}" in plugin_service.plugins:
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
    plugin = plugin.replace("::", "arclet.entari.builtins.")
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
    if not (_plugin := find_plugin(plugin)):
        return False
    publish(PluginUnloaded(_plugin.id))
    _plugin.dispose()
    return True


def enable_plugin(plugin: str):
    """启用指定插件"""
    plugin = plugin.replace("::", "arclet.entari.builtins.")
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
    if not (_plugin := find_plugin(plugin)):
        return False
    _plugin.enable()
    return True


def disable_plugin(plugin: str):
    """禁用指定插件"""
    plugin = plugin.replace("::", "arclet.entari.builtins.")
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
    if not (_plugin := find_plugin(plugin)):
        return False
    _plugin.disable()
    return True


listen = on
