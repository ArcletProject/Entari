import asyncio
import inspect
from typing import Any, Literal, Union, get_args

from arclet.alconna import Alconna, Arparma, Duplication, Empty, output_manager
from arclet.alconna.builtin import generate_duplication
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.letoderea import BLOCK, STOP, Contexts, Param, Propagator, Provider, post
from arclet.letoderea.exceptions import ProviderUnsatisfied
from arclet.letoderea.provider import ProviderFactory
from nepattern.util import CUnionType
from satori import MessageObject
from satori.element import Text
from tarina import LRU
from tarina.generic import get_origin, origin_is_union

from ..config import EntariConfig
from ..event.base import Reply
from ..event.command import CommandOutput, CommandParse, CommandReceive
from ..message import MessageChain
from ..session import Session
from .model import CommandResult, Match, Query


def _is_optional(annotation: Any) -> bool:
    args = get_args(annotation)
    if not args:
        return False
    arg = args[0]
    origin = get_origin(arg)
    if origin_is_union(origin):
        args = get_args(arg)
        return type(None) in args
    return False


def _remove_config_prefix(message: MessageChain):
    if not (command_prefix := EntariConfig.instance.basic.prefix):
        return message
    if message and isinstance(message[0], Text):
        text = message[0].text.lstrip()
        for prefix in command_prefix:
            if not prefix:
                return message
            if text.startswith(prefix):
                message[0] = Text(text[len(prefix) :])
                return message
    return MessageChain()


class MessageJudges(Propagator):
    def __init__(self, need_reply_me: bool, need_notice_me: bool, use_config_prefix: bool):
        self.need_reply_me = need_reply_me
        self.need_notice_me = need_notice_me
        self.use_config_prefix = use_config_prefix

    async def judge(self, ctx: Contexts, message: MessageChain, is_reply_me: bool = False, is_notice_me: bool = False):
        message = message.fork()
        if self.need_reply_me and not is_reply_me:
            return STOP
        if self.need_notice_me and not is_notice_me:
            return STOP
        if self.use_config_prefix and not (message := _remove_config_prefix(message)):
            return STOP
        if "$message_content" in ctx:
            return {"$message_content": message}
        return {"$message": message}

    def compose(self):
        yield self.judge, True, 60


class AlconnaSuppiler(Propagator):
    cmd: Alconna

    def __init__(
        self, cmd: Alconna, cache: "LRU[str, asyncio.Future]", block: bool = True, skip_for_unmatch: bool = True
    ):
        self.cmd = cmd
        self.cache = cache
        self.block = block
        self.skip_for_unmatch = skip_for_unmatch

    async def supply(
        self,
        message: MessageChain,
        origin: MessageObject | None = None,
        session: Session | None = None,
        reply: Reply | None = None,
    ):
        source = origin.id if origin else str(message)
        if source in self.cache:
            future = self.cache[source]
            if future.done():
                res = future.result()
            else:
                res = await future
            if res is None:
                return STOP
            return {"alc_result": res}

        fut = asyncio.Future()
        self.cache[source] = fut
        if session:
            recv = await post(ev := CommandReceive(session, self.cmd, message, reply))
            message = recv.value if recv else ev.content
        with output_manager.capture(self.cmd.name) as cap:
            output_manager.set_action(lambda x: x, self.cmd.name)
            try:
                _res = self.cmd.parse(message)
            except Exception as e:
                _res = Arparma(self.cmd._hash, message, False, error_info=e)
            may_help_text: str | None = cap.get("output", None)
        if not _res.head_matched:
            fut.set_result(None)
            return STOP
        if not may_help_text and not _res.matched and self.skip_for_unmatch:
            fut.set_result(None)
            return BLOCK if self.block else STOP
        if not may_help_text and _res.error_info:
            may_help_text = repr(_res.error_info)
        if session:
            pres = await post(ev := CommandParse(session, self.cmd, _res))
            _res = ev.result
            if pres:
                if isinstance(pres.value, Arparma):
                    _res = pres.value
                elif pres.value is False:
                    return BLOCK if self.block else STOP
        if _res.matched or not may_help_text:
            res = CommandResult(self.cmd, _res, may_help_text)
        elif session:
            _t = str(_res.error_info) if isinstance(_res.error_info, SpecialOptionTriggered) else "error"
            ores = await post(ev := CommandOutput(session, self.cmd, _t, may_help_text))
            msg = MessageChain(ev.content)
            if ores:
                if ores.value is False:
                    msg = None
                elif isinstance(ores.value, str | MessageChain):
                    msg = MessageChain(ores.value)
            if msg:
                await session.send(msg)
            may_help_text = None
            res = CommandResult(self.cmd, _res, may_help_text)
        else:
            res = CommandResult(self.cmd, _res, may_help_text)
        fut.set_result(res)
        if not _res.matched and not may_help_text:
            return BLOCK if self.block else STOP
        return {"alc_result": res}

    def compose(self):
        yield self.supply, True, 70


class AlconnaProvider(Provider[Any]):
    def __init__(self, type_: str, extra: dict | None = None):
        super().__init__()
        self.type = type_
        self.extra = extra or {}

    def __repr__(self):
        return f"AlconnaProvider(type={self.type}, extra={self.extra})"

    async def __call__(self, context: Contexts):
        if "alc_result" not in context:
            if self.type == "args":
                return
            raise ProviderUnsatisfied("alc_result")
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
            default_ = Empty
            if _is_optional(self.extra["anno"]):
                default_ = None
            target = result.result.all_matched_args.get(self.extra["name"], default_)
            return Match(target, target != Empty)
        if self.type == "query":
            default_ = self.extra["query"].result
            if _is_optional(self.extra["anno"]):
                default_ = None
            q = Query(self.extra["query"].path, default_)
            res = result.result.query(q.path, Empty)
            q.available = res != Empty
            if q.available:
                q.result = res  # type: ignore
            elif self.extra["query"].result != Empty:
                q.available = True
            return q
        if self.extra["name"] in result.result.all_matched_args:
            return result.result.all_matched_args[self.extra["name"]]


_seminal = type("_seminal", (object,), {})


class Assign(Propagator):
    def __init__(self, path: str, value: Any = _seminal, or_not: bool = False):
        self.path = path
        self.value = value
        self.or_not = or_not

    async def check(self, alc_result: CommandResult):
        if self.value == _seminal:
            if self.path == "$main" or self.or_not:
                if not alc_result.result.components:
                    return
                return STOP
            if alc_result.result.query(self.path, "\1") == "\1":
                return STOP
        else:
            if alc_result.result.query(self.path) != self.value:
                return STOP
            if self.or_not and alc_result.result.query(self.path) == Empty:
                return
            return STOP

    def compose(self):
        yield self.check, True, 80


class AlconnaProviderFactory(ProviderFactory):
    def validate(self, param: Param):
        annotation = get_origin(param.annotation)
        if annotation in (Union, CUnionType, Literal):
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
            return AlconnaProvider("match", {"name": param.name, "anno": param.annotation})
        if isinstance(param.default, Query):
            return AlconnaProvider("query", {"query": param.default, "anno": param.annotation})
        if annotation is Query:
            return AlconnaProvider("query", {"query": Query(param.name, Empty), "anno": param.annotation})
        return AlconnaProvider("args", {"name": param.name, "anno": param.annotation})
