from __future__ import annotations

from typing import Any

from arclet.alconna import Alconna, command_manager
from arclet.letoderea import BaseAuxiliary, Provider, ProviderFactory

from ..event import MessageEvent
from ..plugin import Plugin, PluginDispatcher
from .model import Match, Query
from .provider import AlconnaProviderFactory, AlconnaSuppiler, Assign, MessageJudger, _seminal


class AlconnaPluginDispatcher(PluginDispatcher):

    def __init__(
        self,
        plugin: Plugin,
        command: Alconna,
        need_tome: bool = False,
        remove_tome: bool = False,
    ):
        self.supplier = AlconnaSuppiler(command, need_tome, remove_tome)
        super().__init__(plugin, MessageEvent)

        self.bind(MessageJudger(), self.supplier)
        self.bind(AlconnaProviderFactory())

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
        return self.register(priority, _auxiliaries, providers)

    def dispose(self):
        super().dispose()
        command_manager.delete(self.supplier.cmd)
        del self.supplier.cmd
        del self.supplier

    Match = Match
    Query = Query


def mount(cmd: Alconna, need_tome: bool = False, remove_tome: bool = False):
    if not (plugin := Plugin.current()):
        raise LookupError("no plugin context found")
    disp = AlconnaPluginDispatcher(plugin, cmd, need_tome, remove_tome)
    return disp
