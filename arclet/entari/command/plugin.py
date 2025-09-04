from __future__ import annotations

from typing import Any

from arclet.alconna import Alconna, command_manager
from arclet.letoderea import define
from arclet.letoderea.provider import TProviders

from ..event.base import MessageCreatedEvent
from ..event.command import CommandExecute
from ..plugin.model import Plugin, PluginDispatcher
from .model import Match, Query
from .provider import AlconnaProviderFactory, AlconnaSuppiler, Assign, MessageJudges, _seminal

exec_pub = define(CommandExecute)
exec_pub.bind(AlconnaProviderFactory())

# fmt: off


class AlconnaPluginDispatcher(PluginDispatcher):
    def __init__(self, plugin: Plugin, command: Alconna, need_reply_me: bool = False, need_notice_me: bool = False, use_config_prefix: bool = True):  # noqa: E501
        plugin._extra.setdefault("commands", []).append((command.prefixes, command.command))
        self.supplier = AlconnaSuppiler(command)
        super().__init__(plugin, MessageCreatedEvent, command.path)
        self.propagators.append(
            MessageJudges(need_reply_me, need_notice_me, use_config_prefix),
        )
        self.propagators.append(self.supplier)
        self.providers.append(AlconnaProviderFactory())

        @plugin.collect
        def dispose():
            command_manager.delete(self.supplier.cmd)
            del self.supplier.cmd
            del self.supplier

    def assign(self, path: str, value: Any = _seminal, or_not: bool = False, priority: int = 16, providers: TProviders | None = None):  # noqa: E501
        assign = Assign(path, value, or_not)
        wrapper = self.register(priority=priority, providers=providers)

        def decorator(func):
            sub = wrapper(func)
            sub.propagate(assign)
            return sub

        return decorator

    def on_execute(self, priority: int = 16, providers: TProviders | None = None):  # noqa: E501
        wrapper = self.plugin._scope.register(priority=priority, providers=providers, publisher=exec_pub)

        def decorator(func):
            sub = wrapper(func)
            sub.propagate(self.supplier)
            return sub

        return decorator

    Match = Match
    Query = Query


def mount(cmd: Alconna, need_reply_me: bool = False, need_notice_me: bool = False, use_config_prefix: bool = True) -> AlconnaPluginDispatcher:  # noqa: E501
    if not (plugin := Plugin.current()):
        raise LookupError("no plugin context found")
    return AlconnaPluginDispatcher(plugin, cmd, need_reply_me, need_notice_me, use_config_prefix)

# fmt: on
