from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Callable, TypeVar, overload
from weakref import ProxyType, finalize, proxy

from arclet.letoderea import BaseAuxiliary, Provider, ProviderFactory, Scope, StepOut, Subscriber, es
from arclet.letoderea.publisher import Publisher, _publishers
from arclet.letoderea.typing import TTarget
from creart import it
from launart import Launart, Service
from tarina import ContextModel

from ..filter import Filter
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
    def __init__(
        self,
        plugin: Plugin,
        event: type[TE],
        name: str | None = None,
    ):
        self.publisher = es.define(event, name)
        self.plugin = plugin
        self._event = event
        self.providers: list[Provider[Any] | ProviderFactory] = []
        self.auxiliaries: list[BaseAuxiliary] = []

    def waiter(
        self,
        *events: Any,
        providers: Sequence[Provider | type[Provider]] | None = None,
        auxiliaries: list[BaseAuxiliary] | None = None,
        priority: int = 15,
        block: bool = False,
    ) -> Callable[[TTarget[R]], StepOut[R]]:
        def wrapper(func: TTarget[R]):
            nonlocal events
            if not events:
                events = (self._event,)
            return StepOut(list(events), func, providers, auxiliaries, priority, block)  # type: ignore

        return wrapper

    @overload
    def register(
        self,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Subscriber: ...

    @overload
    def register(
        self,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def register(
        self,
        func: Callable[..., Any] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ):
        _auxiliaries = auxiliaries or []
        _providers = providers or []
        wrapper = self.plugin._scope.register(
            priority=priority,
            auxiliaries=[*self.auxiliaries, *_auxiliaries],
            providers=[*self.providers, *_providers],
            temporary=temporary,
            publisher=self.publisher,
        )
        if func:
            self.plugin.validate(func)  # type: ignore
            return wrapper(func)

        def decorator(func1, /):
            self.plugin.validate(func1)
            return wrapper(func1)

        return decorator

    @overload
    def once(
        self,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ) -> Subscriber: ...

    @overload
    def once(
        self,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def once(
        self,
        func: Callable[..., Any] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ):
        if func:
            return self.register(func, priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=True)
        return self.register(priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=True)

    on = register
    handle = register

    def __call__(self, func):
        return self.register()(func)


@dataclass
class PluginMetadata:
    name: str
    author: list[str] = field(default_factory=list)
    version: str | None = None
    license: str | None = None
    urls: dict[str, str] | None = None
    description: str | None = None
    icon: str | None = None
    classifier: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    config: Any | None = None

    # standards: list[str] = field(default_factory=list)
    # frameworks: list[str] = field(default_factory=list)
    # component_endpoints: list[str] = field(default_factory=list)


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
    _scope: Scope = field(init=False)

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

    def inject(self, *requires: str):
        plugin = self
        while plugin.id in plugin_service._subplugined:
            plugin = plugin_service.plugins[plugin_service._subplugined[plugin.id]]
        if plugin._metadata:
            plugin._metadata.requirements.extend(requires)
        return self

    def collect(self, *disposes: Callable[[], None]):
        self._dispose_callbacks.extend(disposes)
        return self

    def update_filter(self, allow: dict, deny: dict):
        if not allow and not deny:
            return
        fter = Filter()
        if allow:
            fter = fter.and_(Filter.parse(allow))
        if deny:
            fter = fter.not_(Filter.parse(deny))
        if fter.steps:
            plugin_service.filters[self.id] = fter

    def __post_init__(self):
        self._scope = es.scope(self.id)
        plugin_service.plugins[self.id] = self
        self.update_filter(self.config.pop("$allow", {}), self.config.pop("$deny", {}))
        if "$static" in self.config:
            self.is_static = True
            self.config.pop("$static")
        if self.id not in plugin_service._keep_values:
            plugin_service._keep_values[self.id] = {}
        if self.id not in plugin_service._referents:
            plugin_service._referents[self.id] = set()
        finalize(self, self.dispose)

    def dispose(self):
        plugin_service._unloaded.add(self.id)
        if self._is_disposed:
            return
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
        for callback in self._dispose_callbacks:
            callback()
        self._dispose_callbacks.clear()
        delattr(self.module, "__plugin__")
        for member in self.module.__dict__.values():
            if isinstance(member, ProxyType):
                continue
            if isinstance(member, Subscriber) and not hasattr(member, "__keeping__"):
                member.dispose()
        if self.subplugins:
            subplugs = [i.removeprefix(self.id)[1:] for i in self.subplugins]
            subplugs = (subplugs[:3] + ["..."]) if len(subplugs) > 3 else subplugs
            log.plugin.opt(colors=True).debug(f"disposing sub-plugin <r>{', '.join(subplugs)}</r> of <y>{self.id}</y>")
            for subplug in self.subplugins:
                if subplug not in plugin_service.plugins:
                    continue
                try:
                    plugin_service.plugins[subplug].dispose()
                except Exception as e:
                    log.plugin.opt(colors=True).error(f"failed to dispose sub-plugin <r>{subplug}</r> caused by {e!r}")
                    plugin_service.plugins.pop(subplug, None)
            self.subplugins.clear()
        self._scope.dispose()
        del plugin_service.plugins[self.id]
        del self.module

    def dispatch(self, event: type[TE], name: str | None = None):
        if self.is_static:
            raise StaticPluginDispatchError("static plugin cannot dispatch events")
        return PluginDispatcher(self, event, name=name)

    @overload
    def use(
        self,
        pub: Any,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    @overload
    def use(
        self,
        pub: Any,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ) -> Subscriber: ...

    def use(
        self,
        pub: Any,
        func: Callable[..., Any] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ):
        if self.is_static:
            raise StaticPluginDispatchError("static plugin cannot use events by `Plugin.use`")
        if isinstance(pub, str):
            pid = pub.replace("::", "entari.event/")
        elif isinstance(pub, Publisher):
            pid = pub.id
        else:
            pid = getattr(pub, "__publisher__")
        if pid not in _publishers:
            raise LookupError(f"no publisher found: {pid}")
        disp = PluginDispatcher(self, _publishers[pid].target)
        if func:
            return disp.register(func=func, priority=priority, auxiliaries=auxiliaries, providers=providers)
        return disp.register(priority=priority, auxiliaries=auxiliaries, providers=providers)

    def validate(self, func):
        if func.__module__ != self.module.__name__:
            if "__plugin__" in func.__globals__ and func.__globals__["__plugin__"] is self:
                return
            raise RegisterNotInPluginError(
                f"Handler `{func.__qualname__}` should define "
                f"in the same module as the plugin: {self.module.__name__}. "
                f"Please use the `load_plugin({func.__module__!r})` or `requires({func.__module__!r})`"
                f"or `package({func.__module__!r})` before import it."
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
    def apply(cls, id: str, func: Callable[[RootlessPlugin], Any] | None = None) -> Any:
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


def keeping(id_: str, obj: T, dispose: Callable[[T], None] | None = None) -> T:
    if not (plug := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    if id_ not in plugin_service._keep_values[plug.id]:
        plugin_service._keep_values[plug.id][id_] = KeepingVariable(obj, dispose)
    else:
        obj = plugin_service._keep_values[plug.id][id_].obj  # type: ignore
    return obj
