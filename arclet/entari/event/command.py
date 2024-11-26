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

    __disp_name__ = "entari.event/command_execute"


pub = es.define("entari.event/command_execute", CommandExecute, lambda x: {"command": x.command, "message": x.command})
