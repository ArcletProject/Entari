from dataclasses import dataclass
from typing import Union

from arclet.letoderea import Contexts, Provider, make_event

from ..message import MessageChain


@dataclass
@make_event(name="entari.event/command_execute")
class CommandExecute:
    command: Union[str, MessageChain]

    async def gather(self, context: Contexts):
        if isinstance(self.command, str):
            context["command"] = MessageChain(self.command)
        else:
            context["command"] = self.command

    class CommandProvider(Provider[MessageChain]):
        async def __call__(self, context: Contexts):
            return context.get("command")

    __result_type__: "type[str | MessageChain]" = Union[str, MessageChain]
