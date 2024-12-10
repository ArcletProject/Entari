from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, TypeVar, overload
from weakref import finalize, proxy

from arclet.letoderea import BaseAuxiliary, Provider, ProviderFactory, Publisher, StepOut, Subscriber, es
from arclet.letoderea.publisher import Publishable
from arclet.letoderea.typing import TTarget
from creart import it
from launart import Launart, Service
from tarina import ContextModel

from .._subscriber import SubscribeLoader
from ..event.lifespan import Cleanup, Ready, Startup
from ..logger import log
from .service import plugin_service

if TYPE_CHECKING:
    from ..event.base import BasedEvent

_current_plugin: ContextModel[Plugin] = ContextModel("_current_plugin")

T = TypeVar("T")
R = TypeVar("R")


class RegisterNotInPluginError(Exception):
    pass


class PluginDispatcher:
    def __init__(
        self,
        plugin: Plugin,
        *events: type[BasedEvent],
        predicate: Callable[[BasedEvent], bool] | None = None,
        name: str | None = None,
    ):
        if len(events) == 1:
            name = getattr(events[0], "__publisher__", name)
        id_ = f"#{plugin.id}@{name or id(self)}"
        if name and name in es.publishers:
            self.publisher = es.publishers[name]
        elif id_ in es.publishers:
            self.publisher = es.publishers[id_]
        else:
            self.publisher = Publisher(id_, *events, predicate=predicate)
            es.register(self.publisher)
        self.plugin = plugin
        self._events = events
        self._subscribers: list[SubscribeLoader] = []

    def waiter(
        self,
        *events: type[BasedEvent],
        providers: Sequence[Provider | type[Provider]] | None = None,
        auxiliaries: list[BaseAuxiliary] | None = None,
        priority: int = 15,
        block: bool = False,
    ) -> Callable[[TTarget[R]], StepOut[R]]:
        def wrapper(func: TTarget[R]):
            nonlocal events
            if not events:
                events = self._events
            return StepOut(list(events), func, providers, auxiliaries, priority, block)  # type: ignore

        return wrapper

    def _load(self):
        for sub in self._subscribers:
            sub.load()

    def dispose(self):
        for sub in self._subscribers:
            sub.dispose()
        self._subscribers.clear()

    if TYPE_CHECKING:
        register = Publisher.register
    else:

        def register(self, func: Callable | None = None, **kwargs) -> Any:
            wrapper = self.publisher.register(**kwargs)
            if func:
                self.plugin.validate(func)  # type: ignore
                sub = SubscribeLoader(func, wrapper)
                self._subscribers.append(sub)
                return sub

            def decorator(func1):
                self.plugin.validate(func1)
                sub1 = SubscribeLoader(func1, wrapper)
                self._subscribers.append(sub1)
                return sub1

            return decorator

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

    dispatchers: dict[str, PluginDispatcher] = field(default_factory=dict)
    subplugins: set[str] = field(default_factory=set)
    config: dict[str, Any] = field(default_factory=dict)
    _metadata: PluginMetadata | None = None
    _is_disposed: bool = False

    _services: dict[str, Service] = field(init=False, default_factory=dict)

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

    def _load(self):
        for disp in self.dispatchers.values():
            disp._load()

    async def _startup(self):
        if Startup.__publisher__ in self.dispatchers:
            await self.dispatchers[Startup.__publisher__].publisher.emit(Startup())

    async def _ready(self):
        if Ready.__publisher__ in self.dispatchers:
            await self.dispatchers[Ready.__publisher__].publisher.emit(Ready())

    async def _cleanup(self):
        if Cleanup.__publisher__ in self.dispatchers:
            await self.dispatchers[Cleanup.__publisher__].publisher.emit(Cleanup())

    def __post_init__(self):
        plugin_service.plugins[self.id] = self
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
        delattr(self.module, "__plugin__")
        for member in self.module.__dict__.values():
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
        for disp in self.dispatchers.values():
            disp.dispose()
        self.dispatchers.clear()
        del plugin_service.plugins[self.id]
        del self.module

    def dispatch(
        self, *events: type[BasedEvent], predicate: Callable[[BasedEvent], bool] | None = None, name: str | None = None
    ):
        disp = PluginDispatcher(self, *events, predicate=predicate, name=name)
        if disp.publisher.id in self.dispatchers:
            return self.dispatchers[disp.publisher.id]
        self.dispatchers[disp.publisher.id] = disp
        return disp

    @overload
    def use(
        self,
        pub_id: str | type[Publishable],
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
        pub_id: str | type[Publishable],
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
        pub_id: str | type[Publishable],
        func: Callable[..., Any] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
    ):
        if isinstance(pub_id, str):
            pid = pub_id.replace("::", "entari.event/")
        else:
            pid = getattr(pub_id, "__publisher__")
        if pid not in es.publishers:
            raise LookupError(f"no publisher found: {pid}")
        if not (disp := self.dispatchers.get(pid)):
            disp = PluginDispatcher(self, name=pid)
            self.dispatchers[disp.publisher.id] = disp
        if func:
            return disp.register(func=func, priority=priority, auxiliaries=auxiliaries, providers=providers)
        return disp.register(priority=priority, auxiliaries=auxiliaries, providers=providers)

    def validate(self, func):
        if func.__module__ != self.module.__name__:
            if "__plugin__" in func.__globals__ and func.__globals__["__plugin__"] is self:
                return
            raise RegisterNotInPluginError(
                f"Handler {func.__qualname__} should define "
                f"in the same module as the plugin: {self.module.__name__}. "
                f"Please use the `load_plugin({func.__module__!r})` or "
                f"`package({func.__module__!r})` before import it."
            )

    def proxy(self):
        return proxy(self.module)

    def subproxy(self, sub_id: str):
        return proxy(plugin_service.plugins[sub_id].module)

    def service(self, serv: Service | type[Service]):
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
        if not id.startswith("~"):
            id = f"~{id}"

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
        with _current_plugin.use(self):
            func(self)

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
