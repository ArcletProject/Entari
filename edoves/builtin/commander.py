from typing import Dict, Callable
from arclet.alconna import Alconna
from arclet.letoderea import EventSystem
from arclet.letoderea.utils import run_always_await

from ..main.controller import Controller
from ..main.module import MediumModule
from ..main.typings import TMProtocol
from ..builtin.mah.types import MType
from ..builtin.mah.medium import Message


class CommandParser:
    alconna: Alconna
    param_reactions: Dict[str, Callable]

    def __init__(self, alconna):
        self.alconna = alconna
        self.param_reactions = {}

    def get(self, keyword: str):
        def _wrapper(func):
            self.param_reactions.setdefault(keyword, func)
            return func

        return _wrapper

    async def exec(self, all_args):
        for k, v in self.param_reactions.items():
            if args := all_args.get(k):
                await run_always_await(v, args)


class Commander(MediumModule):
    command_parsers: Controller[str, CommandParser]
    event_system: EventSystem

    def __init__(self, event_system, protocol: TMProtocol):
        super().__init__(protocol)
        self.event_system = event_system
        self.command_parsers = Controller(self.protocol.edoves)

        @self.new_handler(MType.ALL)
        async def command_handler(message: Message):
            # TODO: 对 message.purveyor的权限判断
            for v in self.command_parsers.traverse():
                result = v.alconna.analyse_message(message.content)
                if result.matched:
                    await v.exec(result.all_matched_args)

    def set(self, alconna: Alconna):
        command = CommandParser(alconna)
        self.command_parsers.add(alconna.command, command)
        return command
