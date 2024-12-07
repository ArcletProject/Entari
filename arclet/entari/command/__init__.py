import asyncio
from typing import Callable, Optional, TypeVar, Union, cast, overload

from arclet.alconna import Alconna, Arg, Args, Arparma, CommandMeta, Namespace, command_manager, config, output_manager
from arclet.alconna.tools.construct import AlconnaString, alconna_from_format
from arclet.alconna.typing import TAValue
from arclet.letoderea import BaseAuxiliary, Provider, Publisher, Scope, Subscriber, es
from arclet.letoderea.handler import depend_handler
from arclet.letoderea.provider import ProviderFactory
from arclet.letoderea.typing import TTarget
from nepattern import DirectPattern
from satori.element import At, Text
from tarina.string import split
from tarina.trie import CharTrie

from ..event.command import CommandExecute
from ..event.protocol import MessageCreatedEvent
from ..message import MessageChain
from .argv import MessageArgv  # noqa: F401
from .model import CommandResult, Match, Query
from .plugin import mount
from .provider import AlconnaProviderFactory, AlconnaSuppiler, MessageJudger, get_cmd

T = TypeVar("T")


class EntariCommands:
    __namespace__ = "Entari"

    def __init__(self, need_tome: bool = False, remove_tome: bool = True, use_config_prefix: bool = True):
        self.trie: CharTrie[Subscriber] = CharTrie()
        self.publisher = Publisher("entari.command", MessageCreatedEvent)
        self.publisher.bind(AlconnaProviderFactory())
        self.need_tome = need_tome
        self.remove_tome = remove_tome
        self.use_config_prefix = use_config_prefix
        config.namespaces["Entari"] = Namespace(
            self.__namespace__,
            to_text=lambda x: x.text if x.__class__ is Text else None,
            converter=lambda x: MessageChain(x),
        )

        @es.on(MessageCreatedEvent, auxiliaries=[MessageJudger()])
        async def listener(event: MessageCreatedEvent):
            msg = str(event.content.exclude(At)).lstrip()
            if not msg:
                return
            if matches := list(self.trie.prefixes(msg)):
                await asyncio.gather(*(depend_handler(res.value, event, inner=True) for res in matches if res.value))
                return
            # shortcut
            data = split(msg, " ")
            for value in self.trie.values():
                try:
                    command_manager.find_shortcut(get_cmd(value), data)
                except ValueError:
                    continue
                await depend_handler(value, event, inner=True)

    @property
    def all_helps(self) -> str:
        return command_manager.all_command_help(namespace=self.__namespace__)

    def get_help(self, command: str) -> str:
        return command_manager.get_command(f"{self.__namespace__}::{command}").get_help()

    async def execute(self, message: MessageChain):
        async def _run(target: Subscriber, content: MessageChain):
            aux = next((a for a in target.auxiliaries[Scope.prepare] if isinstance(a, AlconnaSuppiler)), None)
            if not aux:
                return
            with output_manager.capture(aux.cmd.name) as cap:
                output_manager.set_action(lambda x: x, aux.cmd.name)
                try:
                    _res = aux.cmd.parse(content)
                except Exception as e:
                    _res = Arparma(aux.cmd._hash, message, False, error_info=e)
                may_help_text: Optional[str] = cap.get("output", None)
            if _res.matched:
                args = {}
                ctx = {"alc_result": CommandResult(aux.cmd, _res, may_help_text)}
                for param in target.params:
                    args[param.name] = await param.solve(ctx)
                return await target(**args)
            elif may_help_text:
                return may_help_text

        msg = str(message.exclude(At)).lstrip()
        if matches := list(self.trie.prefixes(msg)):
            return await asyncio.gather(*(_run(res.value, message) for res in matches if res.value))
        # shortcut
        data = split(msg, " ")
        res = []
        for value in self.trie.values():
            try:
                command_manager.find_shortcut(get_cmd(value), data)
            except ValueError:
                continue
            res.append(await _run(value, message))
        return res

    def command(
        self,
        command: str,
        help_text: Optional[str] = None,
        need_tome: Optional[bool] = None,
        remove_tome: Optional[bool] = None,
        use_config_prefix: Optional[bool] = None,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
    ):
        class Command(AlconnaString):
            def __call__(_cmd_self, func: TTarget[T]) -> Subscriber[T]:
                return self.on(_cmd_self.build(), need_tome, remove_tome, use_config_prefix, auxiliaries, providers)(
                    func
                )

        return Command(command, help_text)

    @overload
    def on(
        self,
        command: Alconna,
        need_tome: Optional[bool] = None,
        remove_tome: Optional[bool] = None,
        use_config_prefix: Optional[bool] = None,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
    ) -> Callable[[TTarget[T]], Subscriber[T]]: ...

    @overload
    def on(
        self,
        command: str,
        need_tome: Optional[bool] = None,
        remove_tome: Optional[bool] = None,
        use_config_prefix: Optional[bool] = None,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
        *,
        args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
        meta: Optional[CommandMeta] = None,
    ) -> Callable[[TTarget[T]], Subscriber[T]]: ...

    def on(
        self,
        command: Union[Alconna, str],
        need_tome: Optional[bool] = None,
        remove_tome: Optional[bool] = None,
        use_config_prefix: Optional[bool] = None,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
        *,
        args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
        meta: Optional[CommandMeta] = None,
    ) -> Callable[[TTarget[T]], Subscriber[T]]:
        auxiliaries = auxiliaries or []
        providers = providers or []

        def wrapper(func: TTarget[T]) -> Subscriber[T]:
            if isinstance(command, str):
                mapping = {arg.name: arg.value for arg in Args.from_callable(func)[0]}
                mapping.update(args or {})  # type: ignore
                _command = alconna_from_format(command, mapping, meta, union=False)
                _command.reset_namespace(self.__namespace__)
                key = _command.name + "".join(
                    f" {arg.value.target}" for arg in _command.args if isinstance(arg.value, DirectPattern)
                )
                auxiliaries.insert(
                    0,
                    AlconnaSuppiler(
                        _command,
                        self.need_tome if need_tome is None else need_tome,
                        self.remove_tome if remove_tome is None else remove_tome,
                        self.use_config_prefix if use_config_prefix is None else use_config_prefix,
                    ),
                )
                target = self.publisher.register(auxiliaries=auxiliaries, providers=providers)(func)
                self.publisher.remove_subscriber(target)
                self.trie[key] = target

                def _remove(_):
                    self.trie.pop(key, None)  # type: ignore

                target._dispose = _remove
            else:
                auxiliaries.insert(
                    0, AlconnaSuppiler(command, need_tome or self.need_tome, remove_tome or self.remove_tome)
                )
                target = self.publisher.register(auxiliaries=auxiliaries, providers=providers)(func)
                self.publisher.remove_subscriber(target)
                if not isinstance(command.command, str):
                    raise TypeError("Command name must be a string.")
                keys = []
                if not command.prefixes:
                    self.trie[command.command] = target
                    keys.append(command.command)
                elif not all(isinstance(i, str) for i in command.prefixes):
                    raise TypeError("Command prefixes must be a list of string.")
                else:
                    for prefix in cast(list[str], command.prefixes):
                        self.trie[prefix + command.command] = target
                        keys.append(prefix + command.command)

                def _remove(_):
                    for key in keys:
                        self.trie.pop(key, None)  # type: ignore

                target._dispose = _remove
                command.reset_namespace(self.__namespace__)
            return target

        return wrapper


_commands = EntariCommands()


def config_commands(need_tome: bool = False, remove_tome: bool = True, use_config_prefix: bool = True):
    _commands.need_tome = need_tome
    _commands.remove_tome = remove_tome
    _commands.use_config_prefix = use_config_prefix


command = _commands.command
on = _commands.on


async def execute(message: Union[str, MessageChain]):
    res = await es.post(CommandExecute(message))
    if res:
        return res.value


__all__ = ["_commands", "config_commands", "Match", "Query", "execute", "CommandResult", "mount", "command", "on"]
