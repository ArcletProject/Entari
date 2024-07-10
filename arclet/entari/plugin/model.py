from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Callable
from weakref import WeakValueDictionary, finalize

from arclet.letoderea import BaseAuxiliary, Provider, Publisher, StepOut, system_ctx
from arclet.letoderea.builtin.breakpoint import R
from arclet.letoderea.typing import TTarget

if TYPE_CHECKING:
    from ..event import Event

_current_plugin: ContextVar[Plugin | None] = ContextVar("_current_plugin", default=None)

_plugins: dict[str, Plugin] = {}


class PluginDispatcher(Publisher):
    def __init__(
        self,
        plugin: Plugin,
        *events: type[Event],
        predicate: Callable[[Event], bool] | None = None,
    ):
        super().__init__(f"{plugin.id}@{id(plugin)}", *events, predicate=predicate)  # type: ignore
        self.plugin = plugin
        plugin.dispatchers[self.id] = self
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
    __call__ = Publisher.register


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


@dataclass
class Plugin:
    id: str
    module: ModuleType
    dispatchers: WeakValueDictionary[str, PluginDispatcher] = field(default_factory=WeakValueDictionary)
    metadata: PluginMetadata | None = None
    _is_disposed: bool = False

    @staticmethod
    def current() -> Plugin | None:
        return _current_plugin.get()

    def __post_init__(self):
        _plugins[self.id] = self
        finalize(self, self.dispose)

    def dispose(self):
        if self._is_disposed:
            return
        self._is_disposed = True
        for disp in self.dispatchers.values():
            disp.dispose()
        self.dispatchers.clear()
        del _plugins[self.id]
        del self.module
