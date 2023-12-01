import asyncio
import inspect
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    TypeVar,
    Union,
    cast,
    get_args,
    overload,
)
from typing_extensions import TypeAlias
from copy import deepcopy
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
from nepattern import main
from arclet.alconna.args import TAValue
from arclet.alconna.argv import Argv, argv_config, set_default_argv_type
from arclet.alconna.builtin import generate_duplication
from arclet.alconna.tools.construct import AlconnaString, alconna_from_format
from creart import it
from satori import EventType
from satori.element import At, Text
from satori.client import Account
from nepattern import DirectPattern
from pygtrie import CharTrie
from tarina.generic import generic_isinstance, generic_issubclass, get_origin
from tarina.string import split_once
from arclet.letoderea import Provider, Contexts, Param, SupplyAuxiliary, Scope, JudgeAuxiliary, Publisher
from arclet.letoderea.provider import ProviderFactory

from .message import MessageChain
from .event import MessageEvent

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
        return context["$event"].type == EventType.MESSAGE_CREATED.value

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


@dataclass
class AlconnaSuppiler(SupplyAuxiliary):
    cmd: Alconna
    need_tome: bool
    remove_tome: bool

    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        account: Account = context["$account"]
        message: MessageChain = context["$message_content"]
        if self.need_tome and not _is_tome(message, account):
            return
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

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


@dataclass
class AlconnaProvider(Provider[Any]):
    type: str
    extra: dict = field(default_factory=dict)

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
#
#
# class EntariCommands:
#     __namespace__ = "Entari"
#
#     def __init__(self, need_tome: bool = False, remove_tome: bool = False):
#         self.trie: CharTrie = CharTrie()
#         self.publisher = Publisher("EntariCommands", MessageEvent)
#         self.need_tome = need_tome
#         self.remove_tome = remove_tome
#         config.namespaces["Entari"] = Namespace(self.__namespace__)
#
#         @self.publisher.register(auxiliaries=[MessageJudger(), AlconnaSuppiler()])
#         async def listener(event: MessageReceived):
#             msg = str(event.message.content.exclude(Notice)).lstrip()
#             if matches := list(self.trie.prefixes(msg)):
#                 await asyncio.gather(*(self.execute(*res.value, event) for res in matches if res.value))
#                 return
#             # shortcut
#             head, _ = split_once(msg, (" ",))
#             for value in self.trie.values():
#                 try:
#                     command_manager.find_shortcut(value[0], head)
#                 except ValueError:
#                     continue
#                 await self.execute(*value, event)
#
#     @property
#     def all_helps(self) -> str:
#         return command_manager.all_command_help(namespace=self.__namespace__)
#
#     def get_help(self, command: str) -> str:
#         return command_manager.get_command(f"{self.__namespace__}::{command}").get_help()
#
#     async def execute(
#         self,
#         command: Alconna,
#         target: ExecTarget,
#         need_tome: bool,
#         remove_tome: bool,
#         event: MessageReceived
#     ):
#         if (need_tome or self.need_tome) and not _is_tome(event.message.content, event.context):
#             return
#         with output_manager.capture(command.name) as cap:
#             output_manager.set_action(lambda x: x, command.name)
#             msg = event.message.content
#             if remove_tome or self.remove_tome:
#                 msg = _remove_tome(msg, event.context)
#             try:
#                 _res = command.parse(msg)
#             except Exception as e:
#                 _res = Arparma(command.path, event.message.content, False, error_info=e)
#             may_help_text: Optional[str] = cap.get("output", None)
#         if _res.matched:
#             await self.broadcast.Executor(target, [event.Dispatcher, AlconnaDispatcher(command)])
#             target.oplog.clear()
#         elif may_help_text:
#             await event.context.scene.send_message(may_help_text)
#
#     def command(
#         self,
#         command: str,
#         help_text: Optional[str] = None,
#         need_tome: bool = False,
#         remove_tome: bool = False,
#         dispatchers: Optional[list[T_Dispatcher]] = None,
#         decorators: Optional[list[Decorator]] = None,
#     ):
#         class Command(AlconnaString):
#             def __call__(_cmd_self, func: TCallable) -> TCallable:
#                 return self.on(_cmd_self.build(), need_tome, remove_tome, dispatchers, decorators)(func)
#
#         return Command(command, help_text)
#
#     @overload
#     def on(
#         self,
#         command: Alconna,
#         need_tome: bool = False,
#         remove_tome: bool = False,
#         dispatchers: Optional[list[T_Dispatcher]] = None,
#         decorators: Optional[list[Decorator]] = None,
#     ) -> Callable[[TCallable], TCallable]:
#         ...
#
#     @overload
#     def on(
#         self,
#         command: str,
#         need_tome: bool = False,
#         remove_tome: bool = False,
#         dispatchers: Optional[list[T_Dispatcher]] = None,
#         decorators: Optional[list[Decorator]] = None,
#         *,
#         args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
#         meta: Optional[CommandMeta] = None,
#     ) -> Callable[[TCallable], TCallable]:
#         ...
#
#     def on(
#         self,
#         command: Union[Alconna, str],
#         need_tome: bool = False,
#         remove_tome: bool = False,
#         dispatchers: Optional[list[T_Dispatcher]] = None,
#         decorators: Optional[list[Decorator]] = None,
#         *,
#         args: Optional[dict[str, Union[TAValue, Args, Arg]]] = None,
#         meta: Optional[CommandMeta] = None,
#     ) -> Callable[[TCallable], TCallable]:
#         def wrapper(func: TCallable) -> TCallable:
#             target = ExecTarget(func, dispatchers, decorators)
#             if isinstance(command, str):
#                 mapping = {arg.name: arg.value for arg in Args.from_callable(func)[0]}
#                 mapping.update(args or {})  # type: ignore
#                 _command = alconna_from_format(command, mapping, meta, union=False)
#                 _command.reset_namespace(self.__namespace__)
#                 key = _command.name + "".join(
#                     f" {arg.value.target}" for arg in _command.args if isinstance(arg.value, DirectPattern)
#                 )
#                 self.trie[key] = (_command, target, need_tome, remove_tome)
#             else:
#                 if not isinstance(command.command, str):
#                     raise TypeError("Command name must be a string.")
#                 if not command.prefixes:
#                     self.trie[command.command] = (command, target, need_tome, remove_tome)
#                 elif not all(isinstance(i, str) for i in command.prefixes):
#                     raise TypeError("Command prefixes must be a list of string.")
#                 else:
#                     for prefix in cast(list[str], command.prefixes):
#                         self.trie[prefix + command.command] = (command, target, need_tome, remove_tome)
#                 command.reset_namespace(self.__namespace__)
#             return func
#
#         return wrapper
#
#
# __all__ = ["AvillaCommands", "Match"]
