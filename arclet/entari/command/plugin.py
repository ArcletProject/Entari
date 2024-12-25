from __future__ import annotations

from typing import Any

from arclet.alconna import Alconna, command_manager
from arclet.letoderea import BaseAuxiliary, Provider, ProviderFactory, es

from ..event import MessageCreatedEvent
from ..event.command import CommandExecute
from ..plugin.model import Plugin, PluginDispatcher
from .model import Match, Query
from .provider import AlconnaProviderFactory, AlconnaSuppiler, Assign, MessageJudges, _seminal

exec_pub = es.define(CommandExecute)


class AlconnaPluginDispatcher(PluginDispatcher):

    def __init__(
        self,
        plugin: Plugin,
        command: Alconna,
        need_reply_me: bool = False,
        need_notice_me: bool = False,
        use_config_prefix: bool = True,
    ):
        self.supplier = AlconnaSuppiler(command)
        super().__init__(plugin, MessageCreatedEvent, command.path)
        self.scope.bind(
            MessageJudges(need_reply_me, need_notice_me, use_config_prefix),
            self.supplier,
            AlconnaProviderFactory(),
        )

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
        return self.scope.register(priority=priority, auxiliaries=auxiliaries, providers=providers, publisher=exec_pub)

    Match = Match
    Query = Query


def mount(
    cmd: Alconna,
    need_reply_me: bool = False,
    need_notice_me: bool = False,
    use_config_prefix: bool = True,
) -> AlconnaPluginDispatcher:
    if not (plugin := Plugin.current()):
        raise LookupError("no plugin context found")
    disp = AlconnaPluginDispatcher(plugin, cmd, need_reply_me, need_notice_me, use_config_prefix)
    if disp.scope.id in plugin.dispatchers:
        return plugin.dispatchers[disp.scope.id]  # type: ignore
    plugin.dispatchers[disp.scope.id] = disp
    return disp
