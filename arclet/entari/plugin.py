from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib
import inspect
from os import PathLike
from pathlib import Path
from typing import Any, Callable, TypeVar, overload
from typing_extensions import Unpack

from arclet.letoderea import BaseAuxiliary, Provider, Publisher, StepOut, system_ctx
from arclet.letoderea.builtin.breakpoint import R
from arclet.letoderea.typing import TTarget
from loguru import logger

from .event import Event

dispatchers: dict[str, PluginDispatcher] = {}


class PluginDispatcher(Publisher):
    def __init__(
        self,
        plugin: Plugin,
        *events: type[Event],
        predicate: Callable[[Event], bool] | None = None,
    ):
        super().__init__(plugin.name, *events, predicate=predicate)  # type: ignore
        self.plugin = plugin
        if es := system_ctx.get():
            es.register(self)
        else:
            dispatchers[self.id] = self
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

    on = Publisher.register
    handle = Publisher.register


class PluginDispatcherFactory(ABC):
    @abstractmethod
    def dispatch(self, plugin: Plugin) -> PluginDispatcher: ...


MAPPING: dict[type, Callable[..., PluginDispatcherFactory]] = {}

T = TypeVar("T")


def register_factory(cls: type[T], factory: Callable[[T, Unpack[tuple[Any, ...]]], PluginDispatcherFactory]):
    MAPPING[cls] = factory


@dataclass
class Plugin:
    author: list[str] = field(default_factory=list)
    name: str | None = None
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

    _dispatchers: dict[str, PluginDispatcher] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.name = self.name or self.__module__

    def dispatch(self, *events: type[Event], predicate: Callable[[Event], bool] | None = None):
        disp = PluginDispatcher(self, *events, predicate=predicate)
        self._dispatchers[disp.id] = disp
        return disp

    @overload
    def mount(self, factory: PluginDispatcherFactory) -> PluginDispatcher: ...

    @overload
    def mount(self, factory: object, *args, **kwargs) -> PluginDispatcher: ...

    def mount(self, factory: Any, *args, **kwargs):
        if isinstance(factory, PluginDispatcherFactory):
            disp = factory.dispatch(self)
        elif factory_cls := MAPPING.get(factory.__class__):
            disp = factory_cls(factory, *args, **kwargs).dispatch(self)
        else:
            raise TypeError(f"unsupported factory {factory!r}")
        self._dispatchers[disp.id] = disp
        return disp

    def dispose(self):
        for disp in self._dispatchers.values():
            if disp.id in dispatchers:
                del dispatchers[disp.id]
            if es := system_ctx.get():
                es.publishers.pop(disp.id, None)
        self._dispatchers.clear()


def load_plugin(path: str) -> list[Plugin] | None:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
    """
    try:
        imported_module = importlib.import_module(path, path)
        logger.success(f"loaded plugin {path!r}")
        return [m for _, m in inspect.getmembers(imported_module, lambda x: isinstance(x, Plugin))]
    except Exception as e:
        logger.error(f"failed to load plugin {path!r} caused by {e!r}")


def load_plugins(dir_: str | PathLike | Path):
    path = dir_ if isinstance(dir_, Path) else Path(dir_)
    if path.is_dir():
        for p in path.iterdir():
            if p.suffix in (".py", "") and p.stem not in {"__init__", "__pycache__"}:
                load_plugin(".".join(p.parts[:-1:1]) + "." + p.stem)
    elif path.is_file():
        load_plugin(".".join(path.parts[:-1:1]) + "." + path.stem)
