from arclet.alconna import (
    Alconna,
    AlconnaString,
    require_help_send_action,
    all_command_help,
    split_once,
    compile
)
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.handler import await_exec_target
from typing import Callable, Dict, Type, Optional

from .event.message import MessageReceived
from .medium import Message
from ..main.module import BaseModule, ModuleMetaComponent, Component
from ..main.typings import TProtocol
from ..main.utilles.security import EDOVES_DEFAULT
from ...alconna.analysis import Analyser


class CommandParser:
    analyser: Analyser
    param_reaction: Callable

    def __init__(self, alconna: Alconna, func: Callable):
        self.analyser = compile(alconna)
        self.param_reaction = Subscriber(func)

    async def exec(self, params):
        await await_exec_target(self.param_reaction, MessageReceived.param_export(**params))


class CommanderData(ModuleMetaComponent):
    verify_code: str = EDOVES_DEFAULT
    name = "Builtin Commander Module"
    description = "Based on Edoves and Arclet-Alconna"
    usage = """\n@commander.command("test <foo:str>")\ndef test(foo: str):\n\t..."""
    command_namespace: str


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
        alc = AlconnaString(command, *option, custom_types=custom_types, sep=sep)

        def __wrapper(func):
            cmd = CommandParser(alc, func)
            self.parsers.setdefault(alc.headers[0], cmd)
            return command

        return __wrapper

    def shortcut(self, shortcut: str, command: str):
        name = split_once(command, " ")[0]
        cmd = self.parsers.get(name)
        if cmd is None:
            return
        cmd.analyser.alconna.shortcut(shortcut, command)

    def remove_handler(self, command: str):
        del self.parsers[command]


class Commander(BaseModule):
    prefab_metadata = CommanderData
    command_parsers: CommandParsers

    __slots__ = ["command_parsers"]

    def __init__(self, protocol: TProtocol, namespace: Optional[str] = None):
        super().__init__(protocol)
        self.metadata.command_namespace = namespace or self.metadata.protocol.current_scene.scene_name + "_Commander"
        self.command_parsers = CommandParsers(self)
        if self.local_storage.get(self.__class__):
            for k, v in self.local_storage[self.__class__].items():
                self.get_component(CommandParsers).parsers.setdefault(k, v)

        @self.behavior.add_handlers(MessageReceived)
        async def command_message_handler(message: Message):
            async def _action(doc: str):
                await message.set(doc).send()
            for cmd, psr in self.command_parsers.parsers.items():
                require_help_send_action(_action, psr.analyser.alconna.name)
                result = psr.analyser.analyse(message.content)
                if result.matched:
                    await psr.exec(
                        {
                            **result.all_matched_args,
                            "message": message,
                            "sender": message.purveyor,
                            "edoves": self.metadata.protocol.screen.edoves,
                            "scene": self.metadata.protocol.current_scene
                        }
                    )
                    break

        @self.command("help #显示帮助")
        async def _(message: Message):
            await message.set(all_command_help(self.metadata.command_namespace)).send()

    def command(
            __commander_self__,
            command: str,
            *option: str,
            custom_types: Dict[str, Type] = None,
            sep: str = " "
    ):
        alc = AlconnaString(command, *option, custom_types=custom_types, sep=sep).reset_namespace(
            __commander_self__.metadata.command_namespace
        )
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
