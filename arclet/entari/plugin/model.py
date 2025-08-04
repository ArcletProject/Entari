from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Callable, TypeVar, cast, overload
from weakref import finalize, proxy

from arclet.letoderea import Propagator, Provider, ProviderFactory, Scope, StepOut, Subscriber, define, publish
from arclet.letoderea.provider import TProviders
from arclet.letoderea.publisher import Publisher, _publishers
from arclet.letoderea.typing import TTarget
from creart import it
from launart import Launart, Service
from tarina import ContextModel

from ..config import config_model_schema
from ..event.plugin import PluginUnloaded
from ..filter import parse
from ..logger import log
from .service import plugin_service

_current_plugin: ContextModel[Plugin] = ContextModel("_current_plugin")

T = TypeVar("T")
TE = TypeVar("TE")
TS = TypeVar("TS", bound=Service)
R = TypeVar("R")


class RegisterNotInPluginError(Exception):
    pass


class StaticPluginDispatchError(Exception):
    pass


class PluginDispatcher:
    def __init__(self, plugin: Plugin, event: type[TE], name: str | None = None):
        self.publisher = define(event, name=name)
        self.plugin = plugin
        self._event = event
        self.providers: list[Provider[Any] | ProviderFactory] = []
        self.propagators: list[Propagator] = []

    # fmt: off
    def waiter(self, *events: Any, providers: Sequence[Provider | type[Provider]] | None = None, priority: int = 15, block: bool = False) -> Callable[[TTarget[R]], StepOut[R]]:  # noqa: E501
        def wrapper(func: TTarget[R]):
            nonlocal events
            if not events:
                events = (self._event,)
            return StepOut(list(events), func, providers, priority, block)  # type: ignore

        return wrapper  # type: ignore

    @overload
    def register(self, func: Callable[..., Any], *, priority: int = 16, providers: TProviders | None = None, once: bool = False) -> Subscriber: ...  # noqa: E501

    @overload
    def register(self, *, priority: int = 16, providers: TProviders | None = None, once: bool = False) -> Callable[[Callable[..., Any]], Subscriber]: ...  # noqa: E501

    def register(self, func: Callable[..., Any] | None = None, *, priority: int = 16, providers: TProviders | None = None, once: bool = False):  # noqa: E501
        _providers = providers or []
        wrapper = self.plugin._scope.register(priority=priority, providers=[*self.providers, *_providers], once=once, publisher=self.publisher)  # noqa: E501 # type: ignore

        def decorator(func1, /):
            self.plugin.validate(func1)
            sub = wrapper(func1)
            sub.propagates(*self.propagators)
            return sub

        if func:
            return decorator(func)
        return decorator

    @overload
    def once(self, func: Callable[..., Any], *, priority: int = 16, providers: TProviders | None = None) -> Subscriber: ...  # noqa: E501

    @overload
    def once(self, *, priority: int = 16, providers: TProviders | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...  # noqa: E501

    def once(self, func: Callable[..., Any] | None = None, *, priority: int = 16, providers: TProviders | None = None):  # noqa: E501
        if func:
            return self.register(func, priority=priority, providers=providers, once=True)
        return self.register(priority=priority, providers=providers, once=True)

    # fmt: on
    on = register
    handle = register

    def __call__(self, func):
        return self.register()(func)


@dataclass
class PluginMetadata:
    name: str
    """插件名称"""
    author: list[str] = field(default_factory=list)
    """插件作者"""
    version: str | None = None
    """插件版本"""
    license: str | None = None
    """插件许可证"""
    urls: dict[str, str] | None = None
    """插件链接"""
    description: str | None = None
    """插件描述"""
    icon: str | None = None
    """插件图标 URL"""
    classifier: list[str] = field(default_factory=list)
    """插件分类"""
    requirements: list[str] = field(default_factory=list)
    """插件依赖"""
    config: Any | None = None
    """插件配置模型"""
    # standards: list[str] = field(default_factory=list)
    # frameworks: list[str] = field(default_factory=list)
    # component_endpoints: list[str] = field(default_factory=list)

    def get_config_schema(self) -> dict[str, Any]:
        """获取插件配置模型的 JSON Schema"""
        if self.config is None:
            return {}
        return config_model_schema(self.config)


@dataclass
class Plugin:
    id: str
    module: ModuleType

    subplugins: set[str] = field(default_factory=set)
    config: dict[str, Any] = field(default_factory=dict)
    is_static: bool = False
    _metadata: PluginMetadata | None = None
    _is_disposed: bool = False
    _services: dict[str, Service] = field(init=False, default_factory=dict)
    _dispose_callbacks: list[Callable[[], None]] = field(init=False, default_factory=list)
    _config_key: str = field(init=False)
    _scope: Scope = field(init=False)
    _extra: dict[str, Any] = field(default_factory=dict, init=False)  # extra metadata for inspection

    @property
    def available(self) -> bool:
        return not self._is_disposed

    @staticmethod
    def current() -> Plugin:
        try:
            return _current_plugin.get()  # type: ignore
        except LookupError:
            raise LookupError("no plugin context found") from None

    @property
    def metadata(self) -> PluginMetadata | None:
        return self._metadata

    def enable(self):
        self._scope.available = True

    def disable(self):
        self._scope.available = False

    def collect(self, *disposes: Callable[[], None]):
        """收集副作用回收函数"""
        self._dispose_callbacks.extend(disposes)
        return self

    def restore(self):
        """回收所有副作用"""
        for callback in self._dispose_callbacks:
            callback()
        self._dispose_callbacks.clear()

    def __post_init__(self):
        self._scope = Scope.of(self.id)
        plugin_service.plugins[self.id] = self
        self._config_key = self.config.pop("$path", self.id)
        allow = self.config.pop("$allow", {})
        deny = self.config.pop("$deny", {})
        pat = {}
        if allow:
            pat["$and"] = allow
        if deny:
            pat["$not"] = deny
        if pat:
            self._scope.propagators.append(parse(pat))
        if "$static" in self.config:
            self.is_static = True
            self.config.pop("$static")
        if self.id not in plugin_service._keep_values:
            plugin_service._keep_values[self.id] = {}
        if self.id not in plugin_service.referents:
            plugin_service.referents[self.id] = set()
        if self.id not in plugin_service.references:
            plugin_service.references[self.id] = set()
        plugin_service._unloaded.discard(self.id)
        finalize(self, self.dispose, is_cleanup=True)

    def dispose(self, *, is_cleanup: bool = False):
        if not is_cleanup and self.is_static:
            return  # static plugin can only be disposed in cleanup phase
        plugin_service._unloaded.add(self.id)
        if self._is_disposed:
            return
        if not self.id.startswith(".") and self.id not in plugin_service._subplugined:
            log.plugin.debug(f"disposing plugin <y>{self.id}</y>")
        self._is_disposed = True
        for serv in self._services.values():
            try:
                it(Launart).remove_component(serv)
            except ValueError:
                pass
        self._services.clear()
        if self.module.__spec__ and self.module.__spec__.cached:
            Path(self.module.__spec__.cached).unlink(missing_ok=True)
        sys.modules.pop(self.module.__name__, None)
        self.restore()
        delattr(self.module, "__plugin__")
        if self.subplugins:
            subplugs = [i.removeprefix(self.id)[1:] for i in self.subplugins]
            subplugs = (subplugs[:3] + ["..."]) if len(subplugs) > 3 else subplugs
            log.plugin.trace(f"disposing sub-plugin <r>{', '.join(subplugs)}</r> of <y>{self.id}</y>")
            for subplug in self.subplugins:
                if subplug not in plugin_service.plugins:
                    continue
                try:
                    plugin_service.plugins[subplug].dispose(is_cleanup=is_cleanup)
                except Exception as e:
                    log.plugin.error(f"failed to dispose sub-plugin <r>{subplug}</r> caused by {e!r}")
                    plugin_service.plugins.pop(subplug, None)
            self.subplugins.clear()
        if not is_cleanup:
            publish(PluginUnloaded(self.id))
            for ref in plugin_service.references.pop(self.id):
                if ref not in plugin_service.plugins:
                    continue
                if ref not in plugin_service.referents:
                    continue
                if ref in plugin_service._unloaded:
                    continue
                if self.id not in plugin_service.referents[ref]:
                    continue
                plugin_service.referents[ref].remove(self.id)
                if (
                    not plugin_service.referents[ref] and ref not in plugin_service._direct_plugins
                ):  # if no more referents, remove it
                    try:
                        plugin_service.plugins[ref].dispose(is_cleanup=is_cleanup)
                    except Exception as e:
                        log.plugin.error(f"failed to dispose referent plugin <r>{ref}</r> caused by {e!r}")
                        plugin_service.plugins.pop(ref, None)
            for ret in plugin_service.referents[self.id].copy():
                if ret not in plugin_service.plugins:
                    continue
                if ret in plugin_service._unloaded:
                    continue
                try:
                    plugin_service.plugins[ret].dispose(is_cleanup=is_cleanup)
                except Exception as e:
                    log.plugin.error(f"failed to dispose referent plugin <r>{ret}</r> caused by {e!r}")
                    plugin_service.plugins.pop(ret, None)
        self._scope.dispose()
        self._scope.propagators.clear()
        del plugin_service.plugins[self.id]
        del self.module

    def dispatch(self, event: type[TE], name: str | None = None):
        if self.is_static:
            raise StaticPluginDispatchError("static plugin cannot dispatch events")
        return PluginDispatcher(self, event, name=name)

    # fmt: off

    @overload
    def use(self,  pub: str | Publisher, *, priority: int = 16, providers: TProviders | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...  # noqa: E501

    @overload
    def use(self, pub: str | Publisher, func: Callable[..., Any], *, priority: int = 16, providers: TProviders | None = None) -> Subscriber: ...  # noqa: E501

    def use(self, pub: str | Publisher, func: Callable[..., Any] | None = None, *, priority: int = 16, providers: TProviders | None = None):  # noqa: E501
        if self.is_static:
            raise StaticPluginDispatchError("static plugin cannot use events by `Plugin.use`")
        if isinstance(pub, str):
            pid = pub.replace("::", "entari.event/")
        elif isinstance(pub, Publisher):
            pid = pub.id
        else:
            raise TypeError(f"invalid publisher type: {type(pub)}")
        if pid not in _publishers:
            raise LookupError(f"no publisher found: {pid}")
        disp = PluginDispatcher(self, _publishers[pid].target)
        if func:
            return disp.register(func=func, priority=priority, providers=providers)
        return disp.register(priority=priority, providers=providers)

    # fmt: on

    def validate(self, func):
        if func.__module__ != self.module.__name__:
            if "__plugin__" in func.__globals__ and func.__globals__["__plugin__"] is self:
                return
            raise RegisterNotInPluginError(
                f"\nHandler `{func.__qualname__}` from {func.__module__!r} should define "
                f"in the same module as the plugin: {self.module.__name__!r}. "
                "\n\nPlease choose one of the following solutions before import it: "
                f"\n * add {func.__module__!r} to your config file."
                f"\n * write the comment after the import statement line: `# entari: plugin`"
                f"\n * append `load_plugin({func.__module__!r})` before the import statement."
                f"\n * call `requires({func.__module__!r})` before the import statement."
                f"\n * write the comment after the import statement line: `# entari: package`"
                f"\n * call `package({func.__module__!r})` to let it marked as a sub-plugin of `{self.id}`."
            )

    def proxy(self):
        return proxy(self.module)

    def subproxy(self, sub_id: str):
        return proxy(plugin_service.plugins[sub_id].module)

    def service(self, serv: TS | type[TS]) -> TS:
        if isinstance(serv, type):
            serv = serv()
        self._services[serv.id] = serv
        if plugin_service.status.blocking:
            it(Launart).add_component(serv)
        return serv


class RootlessPlugin(Plugin):

    @classmethod
    @overload
    def apply(cls, id: str) -> Callable[[Callable[[RootlessPlugin], Any]], Callable[[], None]]: ...

    @classmethod
    @overload
    def apply(cls, id: str, func: Callable[[RootlessPlugin], Any]) -> Callable[[], None]: ...

    @classmethod
    def apply(cls: type[RootlessPlugin], id: str, func: Callable[[RootlessPlugin], Any] | None = None) -> Any:
        if not id.startswith("."):
            id = f".{id}"

        def dispose():
            if id in plugin_service.plugins:
                plugin_service.plugins[id].dispose()
            else:
                plugin_service._apply.pop(id, None)

        def wrapper(func: Callable[[RootlessPlugin], Any]):
            plugin_service._apply[id] = lambda config: cls(id, func, config)
            return dispose

        if func:
            return wrapper(func)
        return wrapper

    def __init__(self, id: str, func: Callable[[RootlessPlugin], Any], config: dict):
        super().__init__(id, ModuleType(id), config=config)
        setattr(self.module, "__plugin__", self)
        setattr(self.module, "__file__", func.__code__.co_filename)
        self.func = func
        setattr(self.func, "__plugin__", self)
        token = _current_plugin.set(self)
        try:
            func(self)
        finally:
            _current_plugin.reset(token)

    def validate(self, func):
        pass


class KeepingVariable:
    def __init__(self, obj: T, dispose: Callable[[T], None] | None = None):
        self.obj = obj
        self._dispose = dispose
        try:
            setattr(self.obj, "__keeping__", True)
        except AttributeError:
            pass

    def dispose(self):
        if hasattr(self.obj, "dispose"):
            self.obj.dispose()  # type: ignore
        elif self._dispose:
            self._dispose(self.obj)
        del self.obj


@overload
def keeping(id_: str, obj: T, *, dispose: Callable[[T], None] | None = None) -> T: ...


@overload
def keeping(id_: str, *, obj_factory: Callable[[], T], dispose: Callable[[T], None] | None = None) -> T: ...


# fmt: off
def keeping(id_: str, obj: T | None = None, obj_factory: Callable[[], T] | None = None, dispose: Callable[[T], None] | None = None) -> T:  # noqa: E501
# fmt: on
    if not (plug := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    if id_ not in plugin_service._keep_values[plug.id]:
        if obj is None and obj_factory is None:
            raise ValueError("Either `obj` or `obj_factory` must be provided")
        _obj = obj_factory() if obj_factory else obj
        plugin_service._keep_values[plug.id][id_] = KeepingVariable(cast(T, _obj), dispose)
    return plugin_service._keep_values[plug.id][id_].obj  # type: ignore
