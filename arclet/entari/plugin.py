from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import dataclass, field
import importlib
import inspect
from os import PathLike
from pathlib import Path
from typing import Callable

from arclet.letoderea import BaseEvent, Publisher, system_ctx
from loguru import logger

dispatchers = {}


class PluginDispatcher(Publisher):
    def __init__(
        self,
        plugin: Plugin,
        *events: type[BaseEvent],
        predicate: Callable[[BaseEvent], bool] | None = None,
    ):
        super().__init__(plugin.name, *events, predicate=predicate)  # type: ignore
        self.plugin = plugin
        if es := system_ctx.get():
            es.register(self)
        else:
            dispatchers[self.id] = self

    on = Publisher.register
    handle = Publisher.register


class PluginDispatcherFactory(ABC):
    @abstractmethod
    def dispatch(self, plugin: Plugin) -> PluginDispatcher: ...


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

    standards: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    config_endpoints: list[str] = field(default_factory=list)
    component_endpoints: list[str] = field(default_factory=list)

    _dispatchers: dict[str, PluginDispatcher] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.name = self.name or self.__module__

    def dispatch(self, *events: type[BaseEvent], predicate: Callable[[BaseEvent], bool] | None = None):
        disp = PluginDispatcher(self, *events, predicate=predicate)
        self._dispatchers[disp.id] = disp
        return disp

    def mount(self, factory: PluginDispatcherFactory):
        disp = factory.dispatch(self)
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
    with suppress(ModuleNotFoundError):
        imported_module = importlib.import_module(path, path)
        logger.success(f"loaded plugin {path!r}")
        return [m for _, m in inspect.getmembers(imported_module, lambda x: isinstance(x, Plugin))]
    logger.warning(f"failed to load plugin {path!r}")


def load_plugins(dir_: str | PathLike | Path):
    path = dir_ if isinstance(dir_, Path) else Path(dir_)
    if path.is_dir():
        for p in path.iterdir():
            if p.suffix in (".py", "") and p.stem not in {"__init__", "__pycache__"}:
                load_plugin(".".join(p.parts[:-1:1]) + "." + p.stem)
    elif path.is_file():
        load_plugin(".".join(path.parts[:-1:1]) + "." + path.stem)
