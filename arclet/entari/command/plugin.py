from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arclet.alconna import Alconna, Arparma, command_manager, output_manager
from arclet.letoderea import AuxType, BaseAuxiliary, Contexts, Interface, Provider, ProviderFactory, Scope, es

from ..event import MessageCreatedEvent
from ..message import MessageChain
from ..plugin.model import Plugin, PluginDispatcher
from .model import CommandResult, Match, Query
from .provider import AlconnaProviderFactory, AlconnaSuppiler, Assign, MessageJudger, _seminal


@dataclass
class CommandExecute:
    command: str | MessageChain

    async def gather(self, context: Contexts):
        if isinstance(self.command, str):
            context["command"] = MessageChain(self.command)
        else:
            context["command"] = self.command

    class CommandProvider(Provider[MessageChain]):
        async def __call__(self, context: Contexts):
            return context.get("command")


execute_handles = es.define("entari.command/command_execute", CommandExecute)
execute_handles.bind(AlconnaProviderFactory())


class ExecuteJudger(BaseAuxiliary):
    def __init__(self, cmd: Alconna):
        self.cmd = cmd
        super().__init__(AuxType.supply, priority=1)

    async def __call__(self, scope: Scope, interface: Interface):
        message = interface.query(MessageChain, "command")
        with output_manager.capture(self.cmd.name) as cap:
            output_manager.set_action(lambda x: x, self.cmd.name)
            try:
                _res = self.cmd.parse(message)
            except Exception as e:
                _res = Arparma(self.cmd._hash, message, False, error_info=e)
            may_help_text: str | None = cap.get("output", None)
        result = CommandResult(self.cmd, _res, may_help_text)
        return interface.update(alc_result=result)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.command/command_execute_judger"


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
        _auxiliaries.append(ExecuteJudger(self.supplier.cmd))
        return execute_handles.register(priority=priority, auxiliaries=_auxiliaries, providers=providers)

    Match = Match
    Query = Query


def mount(cmd: Alconna, need_tome: bool = False, remove_tome: bool = True) -> AlconnaPluginDispatcher:
    if not (plugin := Plugin.current()):
        raise LookupError("no plugin context found")
    disp = AlconnaPluginDispatcher(plugin, cmd, need_tome, remove_tome)
    if disp.id in plugin.dispatchers:
        return plugin.dispatchers[disp.id]  # type: ignore
    plugin.dispatchers[disp.id] = disp
    return disp
