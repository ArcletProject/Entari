import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
import inspect
from typing import Any, Callable, Generic, Optional, TypeVar, Union, cast, get_args, overload

from arclet.alconna import (
    Alconna,
    Arg,
    Args,
    Arparma,
    CommandMeta,
    Duplication,
    Empty,
    Namespace,
    command_manager,
    config,
    output_manager,
)
from arclet.alconna.args import TAValue
from arclet.alconna.argv import Argv, argv_config, set_default_argv_type
from arclet.alconna.builtin import generate_duplication
from arclet.alconna.tools.construct import AlconnaString, alconna_from_format
from arclet.letoderea import (
    BaseAuxiliary,
    Contexts,
    JudgeAuxiliary,
    Param,
    Provider,
    Publisher,
    Scope,
    Subscriber,
    SupplyAuxiliary,
)
from arclet.letoderea.handler import depend_handler
from arclet.letoderea.provider import ProviderFactory
from nepattern import DirectPattern, main
from pygtrie import CharTrie
from satori.client import Account
from satori.element import At, Text
from tarina.generic import get_origin
from tarina.string import split_once

from .event import MessageEvent
from .message import MessageChain
from .plugin import plugins

T = TypeVar("T")
TCallable = TypeVar("TCallable", bound=Callable[..., Any])


@dataclass
class Match(Generic[T]):
    """
    匹配项，表示参数是否存在于 `all_matched_args` 内

    result (T): 匹配结果

    available (bool): 匹配状态
    """

    result: T
    available: bool


class Query(Generic[T]):
    """
    查询项，表示参数是否可由 `Arparma.query` 查询并获得结果

    result (T): 查询结果

    available (bool): 查询状态

    path (str): 查询路径
    """

    result: T
    available: bool
    path: str

    def __init__(self, path: str, default: Union[T, type[Empty]] = Empty):
        self.path = path
        self.result = default  # type: ignore
        self.available = False

    def __repr__(self):
        return f"Query({self.path}, {self.result})"


@dataclass(frozen=True)
class CommandResult:
    source: Alconna
    result: Arparma
    output: Optional[str] = field(default=None)

    @property
    def matched(self) -> bool:
        return self.result.matched


class MessageArgv(Argv[MessageChain]):
    @staticmethod
    def generate_token(data: list) -> int:
        return hash("".join(i.__repr__() for i in data))


set_default_argv_type(MessageArgv)

argv_config(
    MessageArgv,
    filter_out=[],
    to_text=lambda x: x.text if x.__class__ is Text else None,
    converter=lambda x: MessageChain(x),
)


def _is_tome(message: MessageChain, account: Account):
    if message and isinstance(message[0], At):
        at: At = message[0]  # type: ignore
        if at.id and at.id == account.self_id:
            return True
    return False


def _remove_tome(message: MessageChain, account: Account):
    if _is_tome(message, account):
        message = deepcopy(message)
        message.pop(0)
        if message and isinstance(message[0], Text):
            text = message[0].text.lstrip()  # type: ignore
            if not text:
                message.pop(0)
            else:
                message[0] = Text(text)
        return message
    return message


class MessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[bool]:
        return "$message_content" in context

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class AlconnaSuppiler(SupplyAuxiliary):
    cmd: Alconna
    need_tome: bool
    remove_tome: bool

    def __init__(self, cmd: Alconna, need_tome: bool, remove_tome: bool):
        super().__init__()
        self.cmd = cmd
        self.need_tome = need_tome
        self.remove_tome = remove_tome

    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Union[bool, Contexts]]:
        account: Account = context["$account"]
        message: MessageChain = context["$message_content"]
        if self.need_tome and not _is_tome(message, account):
            return False
        with output_manager.capture(self.cmd.name) as cap:
            output_manager.set_action(lambda x: x, self.cmd.name)
            if self.remove_tome:
                message = _remove_tome(message, account)
            try:
                _res = self.cmd.parse(message)
            except Exception as e:
                _res = Arparma(self.cmd.path, message, False, error_info=e)
            may_help_text: Optional[str] = cap.get("output", None)
        if _res.matched:
            context["alc_result"] = CommandResult(self.cmd, _res, may_help_text)
            return context
        elif may_help_text:
            await account.send(context["$event"], may_help_text)
            return False

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class AlconnaProvider(Provider[Any]):
    def __init__(self, type: str, extra: Optional[dict] = None):
        super().__init__()
        self.type = type
        self.extra = extra or {}

    async def __call__(self, context: Contexts):
        if "alc_result" not in context:
            return
        result: CommandResult = context["alc_result"]
        if self.type == "result":
            return result
        if self.type == "arparma":
            return result.result
        if self.type == "alconna":
            return result.source
        if self.type == "default_duplication":
            return generate_duplication(result.source)(result.result)
        if self.type == "duplication":
            return self.extra["duplication"](result.result)
        if self.type == "match":
            target = result.result.all_matched_args.get(self.extra["name"], Empty)
            return Match(target, target != Empty)
        if self.type == "query":
            q = Query(self.extra["query"].path, self.extra["query"].result)
            result = result.result.query(q.path, Empty)
            q.available = result != Empty
            if q.available:
                q.result = result
            elif self.extra["query"].result != Empty:
                q.available = True
            return q
        if self.extra["name"] in result.result.all_matched_args:
            return result.result.all_matched_args[self.extra["name"]]


class AlconnaProviderFactory(ProviderFactory):
    def validate(self, param: Param):
        annotation = get_origin(param.annotation)
        if annotation in main._Contents:
            annotation = get_origin(get_args(param.annotation)[0])
        if annotation is CommandResult:
            return AlconnaProvider("result")
        if annotation is Arparma:
            return AlconnaProvider("arparma")
        if annotation is Alconna:
            return AlconnaProvider("alconna")
        if annotation is Duplication:
            return AlconnaProvider("default_duplication")
        if inspect.isclass(annotation) and issubclass(annotation, Duplication):
            return AlconnaProvider("duplication", {"duplication": param.annotation})
        if annotation is Match:
            return AlconnaProvider("match", {"name": param.name})
        if isinstance(param.default, Query):
            return AlconnaProvider("query", {"query": param.default})
        return AlconnaProvider("args", {"name": param.name, "anno": param.annotation})


def get_cmd(target: Subscriber):
    return next(a for a in target.auxiliaries[Scope.prepare] if isinstance(a, AlconnaSuppiler)).cmd


class EntariCommands:
    __namespace__ = "Entari"

    def __init__(self, need_tome: bool = False, remove_tome: bool = False):
        self.trie: CharTrie = CharTrie()
        self.publisher = Publisher("EntariCommands", MessageEvent)
        self.publisher.providers.append(AlconnaProviderFactory())
        plugins["~command.EntariCommands"] = self.publisher
        self.need_tome = need_tome
        self.remove_tome = remove_tome
        config.namespaces["Entari"] = Namespace(self.__namespace__)

        @self.publisher.register(auxiliaries=[MessageJudger()])
        async def listener(event: MessageEvent):
            msg = str(event.content.exclude(At)).lstrip()
            if not msg:
                return
            if matches := list(self.trie.prefixes(msg)):
                await asyncio.gather(
                    *(depend_handler(res.value, event, inner=True) for res in matches if res.value)
                )
                return
            # shortcut
            head, _ = split_once(msg, (" ",))
            for value in self.trie.values():
                try:
                    command_manager.find_shortcut(get_cmd(value), head)
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
                    _res = Arparma(aux.cmd.path, message, False, error_info=e)
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
        head, _ = split_once(msg, (" ",))
        res = []
        for value in self.trie.values():
            try:
                command_manager.find_shortcut(get_cmd(value), head)
            except ValueError:
                continue
            res.append(await _run(value, message))
        return res

    def command(
        self,
        command: str,
        help_text: Optional[str] = None,
        need_tome: bool = False,
        remove_tome: bool = False,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]] = None,
    ):
        class Command(AlconnaString):
            def __call__(_cmd_self, func: TCallable) -> TCallable:
                return self.on(_cmd_self.build(), need_tome, remove_tome, auxiliaries, providers)(func)

        return Command(command, help_text)

    @overload
    def on(
        self,
        command: Alconna,
        need_tome: bool = False,
        remove_tome: bool = False,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]] = None,
    ) -> Callable[[TCallable], TCallable]:
        ...

    @overload
    def on(
        self,
        command: str,
        need_tome: bool = False,
        remove_tome: bool = False,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]] = None,
        *,
        args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
        meta: Optional[CommandMeta] = None,
    ) -> Callable[[TCallable], TCallable]:
        ...

    def on(
        self,
        command: Union[Alconna, str],
        need_tome: bool = False,
        remove_tome: bool = False,
        auxiliaries: Optional[list[BaseAuxiliary]] = None,
        providers: Optional[list[Provider, type[Provider], ProviderFactory, type[ProviderFactory]]] = None,
        *,
        args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
        meta: Optional[CommandMeta] = None,
    ) -> Callable[[TCallable], TCallable]:
        auxiliaries = auxiliaries or []
        providers = providers or []

        def wrapper(func: TCallable) -> TCallable:
            if isinstance(command, str):
                mapping = {arg.name: arg.value for arg in Args.from_callable(func)[0]}
                mapping.update(args or {})  # type: ignore
                _command = alconna_from_format(command, mapping, meta, union=False)
                _command.reset_namespace(self.__namespace__)
                key = _command.name + "".join(
                    f" {arg.value.target}" for arg in _command.args if isinstance(arg.value, DirectPattern)
                )
                auxiliaries.insert(
                    0, AlconnaSuppiler(_command, need_tome or self.need_tome, remove_tome or self.remove_tome)
                )
                target = self.publisher.register(auxiliaries=auxiliaries, providers=providers)(func)
                self.publisher.remove_subscriber(target)
                self.trie[key] = target
            else:
                auxiliaries.insert(
                    0, AlconnaSuppiler(command, need_tome or self.need_tome, remove_tome or self.remove_tome)
                )
                target = self.publisher.register(auxiliaries=auxiliaries, providers=providers)(func)
                self.publisher.remove_subscriber(target)
                if not isinstance(command.command, str):
                    raise TypeError("Command name must be a string.")
                if not command.prefixes:
                    self.trie[command.command] = target
                elif not all(isinstance(i, str) for i in command.prefixes):
                    raise TypeError("Command prefixes must be a list of string.")
                else:
                    self.publisher.remove_subscriber(target)
                    for prefix in cast(list[str], command.prefixes):
                        self.trie[prefix + command.command] = target
                command.reset_namespace(self.__namespace__)
            return func

        return wrapper
