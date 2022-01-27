from arclet.alconna import Alconna
from arclet.letoderea.handler import await_exec_target
from typing import Callable, Dict, Type

from .event.message import MessageReceived
from .medium import Message
from ..main.module import BaseModule, ModuleMetaComponent, Component
from ..main.typings import TMProtocol
from ..utilles.security import EDOVES_DEFAULT


class CommandParser:
    alconna: Alconna
    param_reaction: Callable

    def __init__(self, alconna, func: Callable):
        self.alconna = alconna
        self.param_reaction = func

    async def exec(self, params):
        await await_exec_target(self.param_reaction, params)


class CommanderData(ModuleMetaComponent):
    identifier = EDOVES_DEFAULT
    name = "Command of Edoves"
    description = "Based on Edoves and Arclet-Alconna"


class CommandParsers(Component):
    io: "Commander"
    parsers: Dict[str, CommandParser]

    def __init__(self, io: "Commander"):
        super(CommandParsers, self).__init__(io)
        self.parsers = {}

    def command(
            self,
            command: str,
            *option: str,
            custom_types: Dict[str, Type] = None,
            sep: str = " "
    ):
        alc = Alconna.from_string(command, *option, custom_types=custom_types, sep=sep)

        def __wrapper(func):
            cmd = CommandParser(alc, func)
            self.parsers.setdefault(alc.headers[0], cmd)
            return command

        return __wrapper

    def remove_handler(self, command: str):
        del self.parsers[command]


class Commander(BaseModule):
    prefab_metadata = CommanderData
    command_parsers: CommandParsers

    __slots__ = ["command_parsers"]

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        self.command_parsers = CommandParsers(self)
        if self.local_storage.get(self.__class__):
            for k, v in self.local_storage[self.__class__].items():
                self.get_component(CommandParsers).parsers.setdefault(k, v)

        @self.behavior.add_handler(MessageReceived)
        async def command_handler(message: Message, module: Commander):
            for cmd, psr in self.command_parsers.parsers.items():
                result = psr.alconna.analyse_message(message.content)
                if result.matched:
                    await psr.exec(
                        {
                            **result.all_matched_args,
                            "message": message,
                            "sender": message.purveyor,
                            "edoves": module.metadata.protocol.scene.edoves
                        }
                    )
                    break

    def command(
            __commander_self__,
            command: str,
            *option: str,
            custom_types: Dict[str, Type] = None,
            sep: str = " "
    ):
        alc = Alconna.from_string(command, *option, custom_types=custom_types, sep=sep)

        def __wrapper(func):
            cmd = CommandParser(alc, func)
            try:
                __commander_self__.command_parsers.parsers.setdefault(alc.headers[0], cmd)
            except AttributeError:
                if not __commander_self__.local_storage.get(__commander_self__.__class__):
                    __commander_self__.local_storage.setdefault(__commander_self__.__class__, {})
                __commander_self__.local_storage[__commander_self__.__class__].setdefault(alc.headers[0], cmd)
            return command

        return __wrapper
