from dataclasses import dataclass
from typing import Union

from arclet.letoderea import Contexts, Provider, es

from ..message import MessageChain
from .base import BasedEvent


@dataclass
class CommandExecute(BasedEvent):
    command: Union[str, MessageChain]

    async def gather(self, context: Contexts):
        if isinstance(self.command, str):
            context["command"] = MessageChain(self.command)
        else:
            context["command"] = self.command

    class CommandProvider(Provider[MessageChain]):
        async def __call__(self, context: Contexts):
            return context.get("command")

    __publisher__ = "entari.event/command_execute"
    __result_type__: "type[str | MessageChain]" = Union[str, MessageChain]


pub = es.define(CommandExecute.__publisher__, CommandExecute)
