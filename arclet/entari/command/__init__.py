import asyncio
from collections.abc import AsyncGenerator, Awaitable, Generator
from typing import Callable, Optional, TypeVar, Union, cast, overload
from typing_extensions import TypeAlias

from arclet.alconna import Alconna, Arg, Args, CommandMeta, Namespace, command_manager, config
from arclet.alconna.tools.construct import AlconnaString, alconna_from_format
from arclet.alconna.typing import TAValue
import arclet.letoderea as le
from arclet.letoderea import RESULT, ExitState, Scope, Subscriber, make_event
from arclet.letoderea.provider import TProviders, get_providers
from arclet.letoderea.scope import _scopes
from arclet.letoderea.typing import Contexts, Result
from nepattern import DirectPattern
from satori.element import Text
from tarina.trie import CharTrie

from ..config import BasicConfModel, config_model_validate, model_field
from ..event.base import MessageCreatedEvent
from ..event.command import CommandExecute
from ..event.config import ConfigReload
from ..message import MessageChain
from ..plugin import RootlessPlugin, get_plugin, metadata, plugin_config
from ..session import Session
from .argv import MessageArgv  # noqa: F401
from .model import CommandResult, Match, Query
from .plugin import mount
from .provider import AlconnaProviderFactory, AlconnaSuppiler, MessageJudges

_BaseM: TypeAlias = Union[str, MessageChain, None]
_M: TypeAlias = Union[_BaseM, Generator[_BaseM, None, None], AsyncGenerator[_BaseM, None], Awaitable[_BaseM]]
_RM: TypeAlias = Union[_BaseM, AsyncGenerator[_BaseM, None]]
TM = TypeVar("TM", bound=_M)


def get_cmd(target: Subscriber):
    if sup := target.get_propagator(AlconnaSuppiler):
        return sup.cmd
    raise ValueError("Subscriber has no command.")


@make_event(name="entari.event/internal/command_dispatch")
class CommandDispatch:
    providers = [*get_providers(MessageCreatedEvent), *get_providers(CommandExecute), AlconnaProviderFactory()]


async def _after_execute(ctx: Contexts, session: Optional[Session] = None):
    result: _RM = ctx[RESULT]
    if result is not None:
        if isinstance(result, AsyncGenerator):
            msg = None
            async for msg in result:
                if session and msg is not None:
                    await session.send(msg)
            return Result(msg)
        if session:
            await session.send(result)


class EntariCommands:
    __namespace__ = "Entari"

    def __init__(self, need_notice_me: bool = False, need_reply_me: bool = False, use_config_prefix: bool = True):
        self.trie: CharTrie[str] = CharTrie()
        self.scope = Scope("entari.command")
        self.judge = MessageJudges(need_notice_me, need_reply_me, use_config_prefix)
        config.namespaces["Entari"] = Namespace(
            self.__namespace__,
            to_text=lambda x: x.text if x.__class__ is Text else None,
            converter=lambda x: MessageChain(x),
        )
        le.on(CommandExecute, self.execute)

    @property
    def all_helps(self) -> str:
        return command_manager.all_command_help(namespace=self.__namespace__)

    def get_help(self, command: str) -> str:
        return command_manager.get_command(f"{self.__namespace__}::{command}").get_help()

    async def execute(self, message: MessageChain, ctx: Contexts):
        msg = str(message).lstrip()
        if not msg:
            return
        scopes = [self.scope] + [sp for sp in _scopes.values() if sp.available]
        subs = {
            slot[0].id: slot[0]
            for sp in scopes
            for slot in sp.subscribers.values()
            if slot[1] == "entari.event/internal/command_dispatch"
        }
        if matches := list(self.trie.prefixes(msg)):
            subs = {res.value: subs[res.value] for res in matches if res.value in subs}
        results = await asyncio.gather(*(sub.handle(ctx.copy(), inner=True) for sub in subs.values()))
        for result in results:
            if result is ExitState.stop:
                continue
            if result is ExitState.block:
                return
            if result is not None:
                return cast(Union[str, MessageChain], result)

    def command(self, cmd: str, help_text: Optional[str] = None, providers: Optional[TProviders] = None):
        class Command(AlconnaString):
            def __call__(_cmd_self, func: Callable[..., TM]) -> Subscriber[TM]:
                return self.on(_cmd_self.build(), providers)(func)

        return Command(cmd, help_text)

    # fmt: off
    @overload
    def on(self, cmd: Alconna, providers: Optional[TProviders] = None) -> Callable[[Callable[..., TM]], Subscriber[TM]]: ...  # noqa: E501

    @overload
    def on(self, cmd: str, providers: Optional[TProviders] = None, *, args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None, meta: Optional[CommandMeta] = None) -> Callable[[Callable[..., TM]], Subscriber[TM]]: ...  # noqa: E501

    def on(self, cmd: Union[Alconna, str], providers: Optional[TProviders] = None, *, args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None, meta: Optional[CommandMeta] = None) -> Callable[[Callable[..., TM]], Subscriber[TM]]:  # noqa: E501
        # fmt: on
        plg = get_plugin(1, optional=True)
        providers = providers or []

        def wrapper(func: Callable[..., TM]) -> Subscriber[TM]:
            nonlocal meta
            if isinstance(cmd, str):
                if not meta and func.__doc__:
                    meta = CommandMeta(func.__doc__)
                mapping = {arg.name: arg.value for arg in Args.from_callable(func)[0]}
                mapping.update(args or {})  # type: ignore
                _command = alconna_from_format(cmd, mapping, meta, union=False)
                _command.reset_namespace(self.__namespace__)
                key = _command.name + "".join(
                    f" {arg.value.target}" for arg in _command.args if isinstance(arg.value, DirectPattern)
                )
                if plg:
                    target = plg.dispatch(CommandDispatch).handle(func, providers=providers)
                    plg._extra.setdefault("commands", []).append(([], _command.command))
                else:
                    target = self.scope.register(func, CommandDispatch, providers=providers)
                target.propagate(AlconnaSuppiler(_command))
                target.propagate(_after_execute, priority=0)
                self.trie[key] = target.id

                def _remove(_):
                    command_manager.delete(get_cmd(_))
                    self.trie.pop(key, None)  # type: ignore

                target._attach_disposes(_remove)
                return target

            _command = cast(Alconna, cmd)
            if not isinstance(cmd.command, str):
                raise TypeError("Command name must be a string.")
            _command.reset_namespace(self.__namespace__)
            keys = []
            if not _command.prefixes:
                keys.append(_command.command)
            elif not all(isinstance(i, str) for i in _command.prefixes):
                raise TypeError("Command prefixes must be a list of string.")
            else:
                for prefix in cast(list[str], _command.prefixes):
                    keys.append(prefix + _command.command)

            if plg:
                target = plg.dispatch(CommandDispatch).handle(func, providers=providers)
                plg._extra.setdefault("commands", []).append((_command.prefixes, _command.command))
            else:
                target = self.scope.register(func, providers=providers)
            target.propagate(AlconnaSuppiler(_command))
            target.propagate(_after_execute, priority=0)
            for _key in keys:
                self.trie[_key] = target.id

            def _remove(_):
                command_manager.delete(get_cmd(_))
                for _key in keys:
                    self.trie.pop(_key, None)  # type: ignore

            target._attach_disposes(_remove)
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
    res = await le.post(CommandExecute(message))
    if res:
        return res.value


class CommandsConfig(BasicConfModel):
    need_notice_me: bool = model_field(default=False, description="是否需要通知我")
    need_reply_me: bool = model_field(default=False, description="是否需要回复我")
    use_config_prefix: bool = model_field(default=True, description="是否使用配置前缀")


@RootlessPlugin.apply("commands", default=True)
def _(plg: RootlessPlugin):
    metadata(
        "Commands Plugin",
        ["RF-Tar-Railt <rf_tar_railt@qq.com>"],
        config=CommandsConfig,
    )

    conf = plugin_config(CommandsConfig)
    _commands.judge.need_notice_me = conf.need_notice_me
    _commands.judge.need_reply_me = conf.need_reply_me
    _commands.judge.use_config_prefix = conf.use_config_prefix

    plg.dispatch(MessageCreatedEvent).handle(_commands.execute).propagate(_commands.judge)

    @plg.dispatch(ConfigReload)
    def update(event: ConfigReload):
        if event.scope != "plugin":
            return
        if event.key != ".commands":
            return
        new_conf = config_model_validate(CommandsConfig, event.value)
        _commands.judge.need_notice_me = new_conf.need_notice_me
        _commands.judge.need_reply_me = new_conf.need_reply_me
        _commands.judge.use_config_prefix = new_conf.use_config_prefix
        return True


__all__ = ["_commands", "config_commands", "Match", "Query", "execute", "CommandResult", "mount", "command", "on"]
