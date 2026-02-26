from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from typing import TypeAlias, TypeVar, cast, overload
from weakref import WeakValueDictionary

from arclet.alconna import Alconna, Arg, Args, Arparma, CommandMeta, Namespace, command_manager, config
from arclet.alconna.tools.construct import AlconnaString, alconna_from_format
from arclet.alconna.typing import TAValue
import arclet.letoderea as le
from arclet.letoderea import RESULT, ExitState, Scope, Subscriber, make_event
from arclet.letoderea.provider import TProviders, get_providers
from arclet.letoderea.typing import Contexts, Result
from nepattern import DirectPattern
from tarina import LRU
from tarina.trie import CharTrie

from ..config import BasicConfModel, config_model_validate, model_field
from ..event.base import MessageCreatedEvent
from ..event.command import CommandExecute, CommandParse
from ..event.config import ConfigReload
from ..logger import DEBUG_NO, log
from ..message import MessageChain
from ..plugin import RootlessPlugin, get_plugin, metadata, plugin_config
from ..session import Session
from .argv import MessageArgv  # noqa: F401
from .model import CommandResult, Match, Query
from .plugin import mount
from .provider import AlconnaProviderFactory, AlconnaSuppiler, MessageJudges

_BaseM: TypeAlias = str | MessageChain | None
_M: TypeAlias = _BaseM | Generator[_BaseM, None, None] | AsyncGenerator[_BaseM, None] | Awaitable[_BaseM]
_RM: TypeAlias = _BaseM | AsyncGenerator[_BaseM, None]
TM = TypeVar("TM", bound=_M)


def get_cmd(target: Subscriber):
    if sup := target.get_propagator(AlconnaSuppiler):
        return sup.cmd
    raise ValueError("Subscriber has no command.")


@make_event(name="entari.event/internal/command_dispatch")
class CommandDispatch:
    providers = [*get_providers(MessageCreatedEvent), *get_providers(CommandExecute), AlconnaProviderFactory()]


async def _after_execute(ctx: Contexts, session: Session | None = None):
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
        return Result(result)


class EntariCommands:

    def __init__(
        self,
        block: bool = True,
        need_notice_me: bool = False,
        need_reply_me: bool = False,
        use_config_prefix: bool = True,
    ):
        self.trie: CharTrie[list[str]] = CharTrie()
        self.scope = Scope("entari.command")
        self.block = block
        self.judge = MessageJudges(need_notice_me, need_reply_me, use_config_prefix)
        self.subscribers = WeakValueDictionary[str, Subscriber]()
        self._cache = {}

        le.on(CommandExecute, self.execute)

    @property
    def all_helps(self) -> str:
        return command_manager.all_command_help()

    def get_help(self, name: str) -> str:
        return command_manager.get_command(name).get_help()

    async def execute(self, message: MessageChain, ctx: Contexts):
        msg = str(message).lstrip()
        if not msg:
            return
        subs = self.subscribers
        if matches := list(self.trie.prefixes(msg)):
            subs = {sub_id: self.subscribers[sub_id] for res in matches for sub_id in res.value if sub_id in self.subscribers}
        results = await asyncio.gather(*(sub.handle(ctx.copy(), inner=True) for sub in subs.values()))
        for result in results:
            if result is ExitState.stop:
                continue
            if result is ExitState.block:
                return
            if result is not None:
                if self.block:
                    return ExitState.block.finish(cast(str | MessageChain, result))
                return cast(str | MessageChain, result)

    def command(self, cmd: str, help_text: str | None = None, providers: TProviders | None = None):
        class Command(AlconnaString):
            def __call__(_cmd_self, func: Callable[..., TM]) -> Subscriber[TM]:
                return self.on(_cmd_self.build(), providers)(func)

        return Command(cmd, help_text)

    # fmt: off
    @overload
    def on(self, cmd: Alconna, providers: TProviders | None = None) -> Callable[[Callable[..., TM]], Subscriber[TM]]: ...  # noqa: E501

    @overload
    def on(self, cmd: str, providers: TProviders | None = None, *, args: dict[str, TAValue | Args | Arg] | None = None, meta: CommandMeta | None = None) -> Callable[[Callable[..., TM]], Subscriber[TM]]: ...  # noqa: E501

    def on(self, cmd: Alconna | str, providers: TProviders | None = None, *, args: dict[str, TAValue | Args | Arg] | None = None, meta: CommandMeta | None = None) -> Callable[[Callable[..., TM]], Subscriber[TM]]:  # noqa: E501
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
                try:
                    exist = command_manager.get_command(_command.path)
                    if exist != _command:
                        exist.formatter.remove(_command)
                        _command.formatter = _command.formatter.__class__()
                        _command.formatter.add(_command)
                except ValueError:
                    pass
                key = _command.name + "".join(
                    f" {arg.value.target}" for arg in _command.args if isinstance(arg.value, DirectPattern)
                )
                if plg:
                    target = plg.dispatch(CommandDispatch).handle(func, providers=providers)
                    plg._extra.setdefault("commands", []).append(([], _command.command))
                else:
                    target = self.scope.register(func, CommandDispatch, providers=providers)
                target.propagate(AlconnaSuppiler(_command, self._cache.setdefault(_command._hash, LRU(10)), self.block))
                target.propagate(_after_execute, priority=0)
                self.trie.setdefault(key, []).append(target.id)
                self.subscribers[target.id] = target

                def _remove(_):
                    command_manager.delete(get_cmd(_))
                    self.trie[key].remove(target.id)  # type: ignore
                    if not self.trie[key]:
                        self.trie.pop(key, None)  # type: ignore
                    self.subscribers.pop(target.id, None)

                target._attach_disposes(_remove)
                return target

            _command = cast(Alconna, cmd)
            if not isinstance(cmd.command, str):
                raise TypeError("Command name must be a string.")
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
            target.propagate(AlconnaSuppiler(_command, self._cache.setdefault(_command._hash, LRU(10)), self.block))
            target.propagate(_after_execute, priority=0)
            self.subscribers[target.id] = target
            for _key in keys:
                self.trie.setdefault(_key, []).append(target.id)

            def _remove(_):
                command_manager.delete(get_cmd(_))
                self.subscribers.pop(target.id, None)
                for _key in keys:
                    self.trie[_key].remove(target.id)  # type: ignore
                    if not self.trie[_key]:
                        self.trie.pop(_key, None)  # type: ignore

            target._attach_disposes(_remove)
            return target
        return wrapper


_commands = EntariCommands()


def config_commands(
    block: bool = True, need_notice_me: bool = False, need_reply_me: bool = False, use_config_prefix: bool = True
):
    _commands.block = block
    _commands.judge.need_notice_me = need_notice_me
    _commands.judge.need_reply_me = need_reply_me
    _commands.judge.use_config_prefix = use_config_prefix


command = _commands.command
on = _commands.on


async def execute(message: str | MessageChain):
    res = await le.post(CommandExecute(message))
    return res.value if res else None


class CommandsConfig(BasicConfModel):
    block: bool = model_field(default=True, description="是否阻断消息传播")
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
    logger = log.wrapper("[commands]")

    conf = plugin_config(CommandsConfig)
    _commands.block = conf.block
    _commands.judge.need_notice_me = conf.need_notice_me
    _commands.judge.need_reply_me = conf.need_reply_me
    _commands.judge.use_config_prefix = conf.use_config_prefix

    plg.dispatch(MessageCreatedEvent).handle(_commands.execute).propagate(_commands.judge)

    async def _inspect(result: Arparma[MessageChain]):
        logger.debug(f"{result.origin.display()!r} parsed result: {result}")

    if log.levelno <= DEBUG_NO:
        sub = plg.dispatch(CommandParse).handle(_inspect)
    else:
        sub = None

    @plg.dispatch(ConfigReload).handle
    def update(event: ConfigReload):
        nonlocal sub
        if event.scope == "basic":
            if event.key != "log":
                return
            if sub is not None:
                sub.dispose()
            if log.levelno <= DEBUG_NO:
                sub = plg.dispatch(CommandParse).handle(_inspect)
            else:
                sub = None
            return
        if event.key != ".commands":
            return
        new_conf = config_model_validate(CommandsConfig, event.value)
        _commands.block = new_conf.block
        _commands.judge.need_notice_me = new_conf.need_notice_me
        _commands.judge.need_reply_me = new_conf.need_reply_me
        _commands.judge.use_config_prefix = new_conf.use_config_prefix
        return True


__all__ = ["_commands", "config_commands", "Match", "Query", "execute", "CommandResult", "mount", "command", "on"]
