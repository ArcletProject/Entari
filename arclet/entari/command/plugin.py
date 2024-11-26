from __future__ import annotations

from typing import Any

from arclet.alconna import Alconna, command_manager
from arclet.letoderea import BaseAuxiliary, Provider, ProviderFactory

from ..event import MessageCreatedEvent
from ..event.command import pub as execute_handles
from ..plugin.model import Plugin, PluginDispatcher
from .model import Match, Query
from .provider import AlconnaProviderFactory, AlconnaSuppiler, Assign, ExecuteSuppiler, MessageJudger, _seminal

execute_handles.bind(AlconnaProviderFactory())


class AlconnaPluginDispatcher(PluginDispatcher):

    def __init__(
        self,
        plugin: Plugin,
        command: Alconna,
        need_tome: bool = False,
        remove_tome: bool = True,
    ):
        self.supplier = AlconnaSuppiler(command, need_tome, remove_tome)
        super().__init__(plugin, MessageCreatedEvent)

        self.publisher.bind(MessageJudger(), self.supplier)
        self.publisher.bind(AlconnaProviderFactory())

    def assign(
        self,
        path: str,
        value: Any = _seminal,
        or_not: bool = False,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        _auxiliaries = auxiliaries or []
        _auxiliaries.append(Assign(path, value, or_not))
        return self.register(priority=priority, auxiliaries=_auxiliaries, providers=providers)

    def dispose(self):
        super().dispose()
        command_manager.delete(self.supplier.cmd)
        del self.supplier.cmd
        del self.supplier

    def on_execute(
        self,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        _auxiliaries = auxiliaries or []
        _auxiliaries.append(ExecuteSuppiler(self.supplier.cmd))

        def wrapper(func):
            sub = execute_handles.register(func, priority=priority, auxiliaries=_auxiliaries, providers=providers)
            self._subscribers.append(sub)
            return sub

        return wrapper

    Match = Match
    Query = Query


def mount(cmd: Alconna, need_tome: bool = False, remove_tome: bool = True) -> AlconnaPluginDispatcher:
    if not (plugin := Plugin.current()):
        raise LookupError("no plugin context found")
    disp = AlconnaPluginDispatcher(plugin, cmd, need_tome, remove_tome)
    if disp.publisher.id in plugin.dispatchers:
        return plugin.dispatchers[disp.id]  # type: ignore
    plugin.dispatchers[disp.publisher.id] = disp
    return disp
