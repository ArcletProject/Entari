import inspect
from typing import Any, Literal, Optional, Union, get_args

from arclet.alconna import Alconna, Arparma, Duplication, Empty, output_manager
from arclet.alconna.builtin import generate_duplication
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.letoderea import STOP, Contexts, Param, Propagator, Provider, post
from arclet.letoderea.exceptions import ProviderUnsatisfied
from arclet.letoderea.provider import ProviderFactory
from nepattern.util import CUnionType
from satori.element import Text
from tarina.generic import get_origin

from ..config import EntariConfig
from ..event.base import Reply
from ..event.command import CommandOutput, CommandParse, CommandReceive
from ..message import MessageChain
from ..session import Session
from .model import CommandResult, Match, Query


def _remove_config_prefix(message: MessageChain):
    if not (command_prefix := EntariConfig.instance.basic.prefix):
        return message
    if message and isinstance(message[0], Text):
        text = message[0].text.lstrip()  # type: ignore
        for prefix in command_prefix:
            if not prefix:
                return message
            if text.startswith(prefix):
                message = message.copy()
                message[0] = Text(text[len(prefix) :])
                return message
    return MessageChain()


class MessageJudges(Propagator):
    def __init__(self, need_reply_me: bool, need_notice_me: bool, use_config_prefix: bool):
        self.need_reply_me = need_reply_me
        self.need_notice_me = need_notice_me
        self.use_config_prefix = use_config_prefix

    async def judge(self, ctx: Contexts, message: MessageChain, is_reply_me: bool = False, is_notice_me: bool = False):
        if self.need_reply_me and not is_reply_me:
            return STOP
        if self.need_notice_me and not is_notice_me:
            return STOP
        if self.use_config_prefix and not (message := _remove_config_prefix(message)):
            return STOP
        if "$message_content" in ctx:
            return {"$message_content": message}
        return {"message": message}

    def compose(self):
        yield self.judge, True, 60


class AlconnaSuppiler(Propagator):
    cmd: Alconna

    def __init__(self, cmd: Alconna):
        self.cmd = cmd

    async def before_supply(
        self, message: MessageChain, session: Optional[Session] = None, reply: Optional[Reply] = None
    ):
        if session and (recv := await post(CommandReceive(session, self.cmd, message, reply))):
            message = recv.value.copy()
        return {"_message": message}

    async def supply(self, ctx: Contexts):
        try:
            _message: MessageChain = ctx.pop("_message")
        except KeyError:
            raise ProviderUnsatisfied("_message") from None
        with output_manager.capture(self.cmd.name) as cap:
            output_manager.set_action(lambda x: x, self.cmd.name)
            try:
                _res = self.cmd.parse(_message)
            except Exception as e:
                _res = Arparma(self.cmd._hash, _message, False, error_info=e)
            may_help_text: Optional[str] = cap.get("output", None)
        return {"_result": CommandResult(self.cmd, _res, may_help_text)}

    async def after_supply(self, ctx: Contexts, session: Optional[Session] = None):
        try:
            alc_result: CommandResult = ctx.pop("_result")
        except KeyError:
            raise ProviderUnsatisfied("_result") from None
        _res = alc_result.result
        if session and (pres := await post(CommandParse(session, self.cmd, _res))):
            if isinstance(pres.value, Arparma):
                _res = pres.value
            elif not pres.value:
                return STOP
        if _res.matched:
            return {"alc_result": CommandResult(self.cmd, _res, alc_result.output)}
        if alc_result.output:
            if session:
                _t = str(_res.error_info) if isinstance(_res.error_info, SpecialOptionTriggered) else "error"
                if ores := await post(CommandOutput(session, self.cmd, _t, alc_result.output)):
                    if not ores.value:
                        return STOP
                    elif ores.value is True:
                        msg = MessageChain(alc_result.output)
                    else:
                        msg = MessageChain(ores.value)
                else:
                    msg = MessageChain(alc_result.output)
                await session.send(msg)
                return STOP
            return {"alc_result": alc_result}
        return STOP

    def compose(self):
        yield self.before_supply, True, 65
        yield self.supply, True, 70
        yield self.after_supply, True, 75


class AlconnaProvider(Provider[Any]):
    def __init__(self, type_: str, extra: Optional[dict] = None):
        super().__init__()
        self.type = type_
        self.extra = extra or {}

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
            target = result.result.all_matched_args.get(self.extra["name"], Empty)
            return Match(target, target != Empty)
        if self.type == "query":
            q = Query(self.extra["query"].path, self.extra["query"].result)
            res = result.result.query(q.path, Empty)
            q.available = res != Empty
            if q.available:
                q.result = res
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
            return AlconnaProvider("match", {"name": param.name})
        if isinstance(param.default, Query):
            return AlconnaProvider("query", {"query": param.default})
        return AlconnaProvider("args", {"name": param.name, "anno": param.annotation})
