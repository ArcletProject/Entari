from __future__ import annotations

from collections.abc import Awaitable
from contextvars import ContextVar
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable
from weakref import finalize

from arclet.letoderea import BaseAuxiliary, Provider, Publisher, StepOut, system_ctx
from arclet.letoderea.builtin.breakpoint import R
from arclet.letoderea.typing import TTarget
from satori.client import Account
from tarina import init_spec

from .service import service

if TYPE_CHECKING:
    from ..event import Event

_current_plugin: ContextVar[Plugin | None] = ContextVar("_current_plugin", default=None)


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

    on = Publisher.register
    handle = Publisher.register

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
    metadata: PluginMetadata | None = None
    _is_disposed: bool = False

    _preparing: list[_Lifespan] = field(init=False, default_factory=list)
    _cleanup: list[_Lifespan] = field(init=False, default_factory=list)
    _connected: list[_AccountUpdate] = field(init=False, default_factory=list)
    _disconnected: list[_AccountUpdate] = field(init=False, default_factory=list)

    def on_prepare(self, func: _Lifespan):
        self._preparing.append(func)
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
        return _current_plugin.get()  # type: ignore

    def __post_init__(self):
        service.plugins[self.id] = self
        finalize(self, self.dispose)

    @init_spec(PluginMetadata, True)
    def meta(self, metadata: PluginMetadata):
        self.metadata = metadata
        return self

    def dispose(self):
        if self._is_disposed:
            return
        self._is_disposed = True
        for disp in self.dispatchers.values():
            disp.dispose()
        self.dispatchers.clear()
        del service.plugins[self.id]
        del self.module

    def dispatch(self, *events: type[Event], predicate: Callable[[Event], bool] | None = None):
        disp = PluginDispatcher(self, *events, predicate=predicate)
        if disp.id in self.dispatchers:
            return self.dispatchers[disp.id]
        self.dispatchers[disp.id] = disp
        return disp
