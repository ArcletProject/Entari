from __future__ import annotations

from collections.abc import Awaitable
from contextvars import ContextVar
from dataclasses import dataclass, field
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, TypeVar
from weakref import finalize, ref

from arclet.letoderea import BaseAuxiliary, Provider, Publisher, StepOut, system_ctx
from arclet.letoderea.builtin.breakpoint import R
from arclet.letoderea.typing import TTarget
from creart import it
from launart import Launart, Service
from satori.client import Account

from .service import plugin_service

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
    submodules: dict[str, ModuleType] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    _metadata: PluginMetadata | None = None
    _is_disposed: bool = False

    _preparing: list[_Lifespan] = field(init=False, default_factory=list)
    _cleanup: list[_Lifespan] = field(init=False, default_factory=list)
    _connected: list[_AccountUpdate] = field(init=False, default_factory=list)
    _disconnected: list[_AccountUpdate] = field(init=False, default_factory=list)

    _services: dict[str, Service] = field(init=False, default_factory=dict)

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
        finalize(self, self.dispose)

    def dispose(self):
        plugin_service._unloaded.add(self.id)
        if self._is_disposed:
            return
        self._is_disposed = True
        if self.module.__spec__ and self.module.__spec__.cached:
            Path(self.module.__spec__.cached).unlink(missing_ok=True)
        sys.modules.pop(self.module.__name__, None)
        delattr(self.module, "__plugin__")
        for submod in self.submodules.values():
            delattr(submod, "__plugin__")
            sys.modules.pop(submod.__name__, None)
            plugin_service._submoded.pop(submod.__name__, None)
            if submod.__spec__ and submod.__spec__.cached:
                Path(submod.__spec__.cached).unlink(missing_ok=True)
        self.submodules.clear()
        for disp in self.dispatchers.values():
            disp.dispose()
        self.dispatchers.clear()
        del plugin_service.plugins[self.id]
        del self.module
        for serv in self._services.values():
            try:
                it(Launart).remove_component(serv)
            except ValueError:
                pass
        self._services.clear()

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
        return _ProxyModule(self.id)

    def subproxy(self, sub_id: str):
        return _ProxyModule(self.id, sub_id)

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


class _ProxyModule(ModuleType):

    def __get_module(self) -> ModuleType:
        mod = self.__origin()
        if not mod:
            raise NameError(f"Plugin {self.__plugin_id!r} is not loaded")
        return mod

    def __init__(self, plugin_id: str, sub_id: str | None = None) -> None:
        self.__plugin_id = plugin_id
        self.__sub_id = sub_id
        if self.__plugin_id not in plugin_service.plugins:
            raise NameError(f"Plugin {self.__plugin_id!r} is not loaded")
        if self.__sub_id:
            self.__origin = ref(plugin_service.plugins[self.__plugin_id].submodules[self.__sub_id])
        else:
            self.__origin = ref(plugin_service.plugins[self.__plugin_id].module)
        super().__init__(self.__get_module().__name__)
        self.__doc__ = self.__get_module().__doc__
        self.__file__ = self.__get_module().__file__
        self.__loader__ = self.__get_module().__loader__
        self.__package__ = self.__get_module().__package__
        if path := getattr(self.__get_module(), "__path__", None):
            self.__path__ = path
        self.__spec__ = self.__get_module().__spec__

    def __repr__(self):
        if self.__sub_id:
            return f"<ProxyModule {self.__sub_id!r}>"
        return f"<ProxyModule {self.__plugin_id!r}>"

    @property
    def __dict__(self) -> dict[str, Any]:
        return self.__get_module().__dict__

    def __getattr__(self, name: str):
        if name in (
            "_ProxyModule__plugin_id",
            "_ProxyModule__sub_id",
            "_ProxyModule__origin",
            "__name__",
            "__doc__",
            "__file__",
            "__loader__",
            "__package__",
            "__path__",
            "__spec__",
        ):
            return super().__getattribute__(name)
        if self.__plugin_id not in plugin_service.plugins:
            raise NameError(f"Plugin {self.__plugin_id!r} is not loaded")
        if plug := inspect.currentframe().f_back.f_globals.get("__plugin__"):  # type: ignore
            if plug.id != self.__plugin_id:
                plugin_service._referents[self.__plugin_id].add(plug.id)
        elif plug := inspect.currentframe().f_back.f_back.f_globals.get("__plugin__"):  # type: ignore
            if plug.id != self.__plugin_id:
                plugin_service._referents[self.__plugin_id].add(plug.id)
        return getattr(self.__get_module(), name)

    def __setattr__(self, name: str, value):
        if name in (
            "_ProxyModule__plugin_id",
            "_ProxyModule__sub_id",
            "_ProxyModule__origin",
            "__name__",
            "__doc__",
            "__file__",
            "__loader__",
            "__package__",
            "__path__",
            "__spec__",
        ):
            return super().__setattr__(name, value)
        setattr(self.__get_module(), name, value)
