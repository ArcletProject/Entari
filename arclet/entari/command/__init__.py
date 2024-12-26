import asyncio
from typing import Callable, Optional, TypeVar, Union, cast, overload

from arclet.alconna import Alconna, Arg, Args, CommandMeta, Namespace, command_manager, config
from arclet.alconna.tools.construct import AlconnaString, alconna_from_format
from arclet.alconna.typing import TAValue
from arclet.letoderea import BaseAuxiliary, Provider, Scope, Subscriber, es
from arclet.letoderea.handler import generate_contexts
from arclet.letoderea.provider import ProviderFactory, get_providers
from arclet.letoderea.typing import Contexts, TTarget
from nepattern import DirectPattern
from satori.element import Text
from tarina.string import split
from tarina.trie import CharTrie

from ..event.base import MessageCreatedEvent
from ..event.command import CommandExecute
from ..event.config import ConfigReload
from ..message import MessageChain
from ..plugin import RootlessPlugin, _current_plugin
from ..session import Session
from .argv import MessageArgv  # noqa: F401
from .model import CommandResult, Match, Query
from .plugin import mount
from .provider import AlconnaProviderFactory, AlconnaSuppiler, MessageJudges, get_cmd

TM = TypeVar("TM", str, MessageChain)


class EntariCommands:
    __namespace__ = "Entari"

    def __init__(self, need_notice_me: bool = False, need_reply_me: bool = False, use_config_prefix: bool = True):
        self.trie: CharTrie[Subscriber[Optional[Union[str, MessageChain]]]] = CharTrie()
        self.scope = Scope("entari.command")
        self.scope.bind(*get_providers(MessageCreatedEvent), AlconnaProviderFactory())
        self.judge = MessageJudges(need_notice_me, need_reply_me, use_config_prefix)
        config.namespaces["Entari"] = Namespace(
            self.__namespace__,
            to_text=lambda x: x.text if x.__class__ is Text else None,
            converter=lambda x: MessageChain(x),
        )
        es.on(CommandExecute, self.execute)

    @property
    def all_helps(self) -> str:
        return command_manager.all_command_help(namespace=self.__namespace__)

    def get_help(self, command: str) -> str:
        return command_manager.get_command(f"{self.__namespace__}::{command}").get_help()

    async def handle(self, session: Session, message: MessageChain, ctx: Contexts):
        msg = str(message).lstrip()
        if not msg:
            return
        if matches := list(self.trie.prefixes(msg)):
            results = await asyncio.gather(*(res.value.handle(ctx.copy()) for res in matches if res.value))
            for result in results:
                if result is not None:
                    await session.send(result)
            return
        # shortcut
        data = split(msg, " ")
        for value in self.trie.values():
            try:
                command_manager.find_shortcut(get_cmd(value), data)
            except ValueError:
                continue
            result = await value.handle(ctx.copy())
            if result is not None:
                await session.send(result)

    async def execute(self, event: CommandExecute):
        ctx = await generate_contexts(event)
        msg = str(event.command)
        if matches := list(self.trie.prefixes(msg)):
            results = await asyncio.gather(*(res.value.handle(ctx.copy(), inner=True) for res in matches if res.value))
            for result in results:
                if result is not None:
                    return result
        data = split(msg, " ")
        for value in self.trie.values():
            try:
                command_manager.find_shortcut(get_cmd(value), data)
            except ValueError:
                continue
            result = await value.handle(ctx.copy(), inner=True)
            if result is not None:
                return result

    def command(
        self,
        command: str,
        help_text: Optional[str] = None,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
    ):
        class Command(AlconnaString):
            def __call__(_cmd_self, func: TTarget[Optional[TM]]) -> Subscriber[Optional[TM]]:
                return self.on(_cmd_self.build(), auxiliaries, providers)(func)

        return Command(command, help_text)

    @overload
    def on(
        self,
        command: Alconna,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
    ) -> Callable[[TTarget[Optional[TM]]], Subscriber[Optional[TM]]]: ...

    @overload
    def on(
        self,
        command: str,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
        *,
        args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
        meta: Optional[CommandMeta] = None,
    ) -> Callable[[TTarget[Optional[TM]]], Subscriber[Optional[TM]]]: ...

    def on(
        self,
        command: Union[Alconna, str],
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Union[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]]] = None,
        *,
        args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
        meta: Optional[CommandMeta] = None,
    ) -> Callable[[TTarget[Optional[TM]]], Subscriber[Optional[TM]]]:
        auxiliaries = auxiliaries or []
        if plg := _current_plugin.get():
            auxiliaries.extend(plg._scope.auxiliaries)
        providers = providers or []

        def wrapper(func: TTarget[Optional[TM]]) -> Subscriber[Optional[TM]]:
            if isinstance(command, str):
                mapping = {arg.name: arg.value for arg in Args.from_callable(func)[0]}
                mapping.update(args or {})  # type: ignore
                _command = alconna_from_format(command, mapping, meta, union=False)
                _command.reset_namespace(self.__namespace__)
                key = _command.name + "".join(
                    f" {arg.value.target}" for arg in _command.args if isinstance(arg.value, DirectPattern)
                )
                auxiliaries.insert(0, AlconnaSuppiler(_command))
                target = self.scope.register(func, auxiliaries=auxiliaries, providers=providers)
                self.scope.remove_subscriber(target)
                self.trie[key] = target

                def _remove(_):
                    command_manager.delete(get_cmd(_))
                    self.trie.pop(key, None)  # type: ignore

                target._dispose = _remove
                return target

            _command = cast(Alconna, command)
            if not isinstance(command.command, str):
                raise TypeError("Command name must be a string.")
            _command.reset_namespace(self.__namespace__)
            auxiliaries.insert(0, AlconnaSuppiler(_command))
            keys = []
            if not _command.prefixes:
                keys.append(_command.command)
            elif not all(isinstance(i, str) for i in _command.prefixes):
                raise TypeError("Command prefixes must be a list of string.")
            else:
                for prefix in cast(list[str], _command.prefixes):
                    keys.append(prefix + _command.command)

            target = self.scope.register(func, auxiliaries=auxiliaries, providers=providers)
            self.scope.remove_subscriber(target)

            for _key in keys:
                self.trie[_key] = target

            def _remove(_):
                command_manager.delete(get_cmd(_))
                for _key in keys:
                    self.trie.pop(_key, None)  # type: ignore

            target._dispose = _remove
            return target

        return wrapper


_commands = EntariCommands()


def config_commands(need_notice_me: bool = False, need_reply_me: bool = False, use_config_prefix: bool = True):
    _commands.judge.need_notice_me = need_notice_me
    _commands.judge.need_reply_me = need_reply_me
    _commands.judge.use_config_prefix = use_config_prefix


command = _commands.command
on = _commands.on


async def execute(message: Union[str, MessageChain]):
    res = await es.post(CommandExecute(message))
    if res:
        return res.value


@RootlessPlugin.apply("commands")
def _(plg: RootlessPlugin):
    if "need_notice_me" in plg.config:
        _commands.judge.need_notice_me = plg.config["need_notice_me"]
    if "need_reply_me" in plg.config:
        _commands.judge.need_reply_me = plg.config["need_reply_me"]
    if "use_config_prefix" in plg.config:
        _commands.judge.use_config_prefix = plg.config["use_config_prefix"]

    plg.dispatch(MessageCreatedEvent).handle(_commands.handle, auxiliaries=[_commands.judge])

    @plg.use(ConfigReload)
    def update(event: ConfigReload):
        if event.scope != "plugin":
            return
        if event.key != ".commands":
            return
        if "need_notice_me" in event.value:
            _commands.judge.need_notice_me = event.value["need_notice_me"]
        if "need_reply_me" in event.value:
            _commands.judge.need_reply_me = event.value["need_reply_me"]
        if "use_config_prefix" in event.value:
            _commands.judge.use_config_prefix = event.value["use_config_prefix"]
        return True


__all__ = ["_commands", "config_commands", "Match", "Query", "execute", "CommandResult", "mount", "command", "on"]
