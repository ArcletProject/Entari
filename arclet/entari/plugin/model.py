from __future__ import annotations

from collections.abc import Awaitable
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, TypeVar
from weakref import finalize, proxy

from arclet.letoderea import BaseAuxiliary, Provider, Publisher, StepOut, system_ctx
from arclet.letoderea.builtin.breakpoint import R
from arclet.letoderea.typing import TTarget
from creart import it
from launart import Launart, Service
from loguru import logger
from satori.client import Account

from .service import PluginLifecycleService, plugin_service

if TYPE_CHECKING:
    from ..event import Event

_current_plugin: ContextVar[Plugin] = ContextVar("_current_plugin")


class RegisterNotInPluginError(Exception):
    pass


class PluginDispatcher(Publisher):
    def __init__(
        self,
        plugin: Plugin,
        *events: type[Event],
        predicate: Callable[[Event], bool] | None = None,
    ):
        super().__init__(f"{plugin.id}@{id(self)}", *events, predicate=predicate)  # type: ignore
        self.plugin = plugin
        self._run_by_system = False
        if es := system_ctx.get():
            es.register(self)
            self._run_by_system = True
        self._events = events

    def waiter(
        self,
        *events: type[Event],
        providers: list[Provider | type[Provider]] | None = None,
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

    def dispose(self):
        if self._run_by_system:
            if es := system_ctx.get():
                es.publishers.pop(self.id, None)
            self._run_by_system = False
        self.subscribers.clear()

    if TYPE_CHECKING:
        register = Publisher.register
    else:

        def register(self, *args, **kwargs):
            wrapper = super().register(*args, **kwargs)

            def decorator(func):
                self.plugin.validate(func)
                return wrapper(func)

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
    dependencies: list[str] = field(default_factory=list)

    # standards: list[str] = field(default_factory=list)
    # frameworks: list[str] = field(default_factory=list)
    # config_endpoints: list[str] = field(default_factory=list)
    # component_endpoints: list[str] = field(default_factory=list)


_Lifespan = Callable[..., Awaitable[Any]]
_AccountUpdate = Callable[[Account], Awaitable[Any]]


@dataclass
class Plugin:
    id: str
    module: ModuleType
    dispatchers: dict[str, PluginDispatcher] = field(default_factory=dict)
    subplugins: set[str] = field(default_factory=set)
    config: dict[str, Any] = field(default_factory=dict)
    _metadata: PluginMetadata | None = None
    _is_disposed: bool = False

    _preparing: list[_Lifespan] = field(init=False, default_factory=list)
    _cleanup: list[_Lifespan] = field(init=False, default_factory=list)
    _running: list[_Lifespan] = field(init=False, default_factory=list)
    _connected: list[_AccountUpdate] = field(init=False, default_factory=list)
    _disconnected: list[_AccountUpdate] = field(init=False, default_factory=list)

    _lifecycle: PluginLifecycleService | None = field(init=False, default=None)
    _services: dict[str, Service] = field(init=False, default_factory=dict)

    def on_prepare(self, func: _Lifespan):
        self._preparing.append(func)
        return func

    def on_running(self, func: _Lifespan):
        self._running.append(func)
        return func

    def on_cleanup(self, func: _Lifespan):
        self._cleanup.append(func)
        return func

    def on_connect(self, func: _AccountUpdate):
        self._connected.append(func)
        return func

    def on_disconnect(self, func: _AccountUpdate):
        self._disconnected.append(func)
        return func

    @staticmethod
    def current() -> Plugin:
        try:
            return _current_plugin.get()  # type: ignore
        except LookupError:
            raise LookupError("no plugin context found") from None

    @property
    def metadata(self) -> PluginMetadata | None:
        return self._metadata

    def __post_init__(self):
        plugin_service.plugins[self.id] = self
        if self.id not in plugin_service._keep_values:
            plugin_service._keep_values[self.id] = {}
        if self.id not in plugin_service._referents:
            plugin_service._referents[self.id] = set()
        if self.id not in plugin_service._subplugined:
            self._lifecycle = PluginLifecycleService(self.id)
            if plugin_service.status.blocking and (self._preparing or self._running or self._cleanup):
                it(Launart).add_component(self._lifecycle)
        finalize(self, self.dispose)

    def dispose(self):
        plugin_service._unloaded.add(self.id)
        if self._is_disposed:
            return
        self._is_disposed = True
        if self._lifecycle and self._lifecycle.status.prepared:
            it(Launart).remove_component(self._lifecycle)
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
        if self.subplugins:
            subplugs = [i.removeprefix(self.id)[1:] for i in self.subplugins]
            subplugs = (subplugs[:3] + ["..."]) if len(subplugs) > 3 else subplugs
            logger.debug(f"disposing sub-plugin {', '.join(subplugs)} of {self.id}")
            for subplug in self.subplugins:
                if subplug not in plugin_service.plugins:
                    continue
                try:
                    plugin_service.plugins[subplug].dispose()
                except Exception as e:
                    logger.error(f"failed to dispose sub-plugin {subplug} caused by {e!r}")
                    plugin_service.plugins.pop(subplug, None)
            self.subplugins.clear()
        for disp in self.dispatchers.values():
            disp.dispose()
        self.dispatchers.clear()
        del plugin_service.plugins[self.id]
        del self.module

    def dispatch(self, *events: type[Event], predicate: Callable[[Event], bool] | None = None):
        disp = PluginDispatcher(self, *events, predicate=predicate)
        if disp.id in self.dispatchers:
            return self.dispatchers[disp.id]
        self.dispatchers[disp.id] = disp
        return disp

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


class KeepingVariable:
    def __init__(self, obj: T, dispose: Callable[[T], None] | None = None):
        self.obj = obj
        self._dispose = dispose

    def dispose(self):
        if hasattr(self.obj, "dispose"):
            self.obj.dispose()  # type: ignore
        elif self._dispose:
            self._dispose(self.obj)
        del self.obj


T = TypeVar("T")


def keeping(id_: str, obj: T, dispose: Callable[[T], None] | None = None) -> T:
    if not (plug := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    if id_ not in plugin_service._keep_values[plug.id]:
        plugin_service._keep_values[plug.id][id_] = KeepingVariable(obj, dispose)
    else:
        obj = plugin_service._keep_values[plug.id][id_].obj  # type: ignore
    return obj
