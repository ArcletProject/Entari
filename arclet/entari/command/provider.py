import inspect
from typing import Any, Literal, Optional, Union, get_args

from arclet.alconna import Alconna, Arparma, Duplication, Empty, output_manager
from arclet.alconna.builtin import generate_duplication
from arclet.letoderea import BaseAuxiliary, Contexts, Interface, Param, Provider, Subscriber
from arclet.letoderea.provider import ProviderFactory
from nepattern.util import CUnionType
from satori.element import Text
from tarina.generic import get_origin

from ..config import EntariConfig
from ..message import MessageChain
from ..session import Session
from .model import CommandResult, Match, Query


def _remove_config_prefix(message: MessageChain):
    if not (command_prefix := EntariConfig.instance.basic.get("prefix", [])):
        return message
    if message and isinstance(message[0], Text):
        text = message[0].text  # type: ignore
        for prefix in command_prefix:
            if not prefix:
                return message
            if text.startswith(prefix):
                message = message.copy()
                message[0] = Text(text[len(prefix) :])
                return message
    return MessageChain()


class MessageJudges(BaseAuxiliary):
    def __init__(self, need_reply_me: bool, need_notice_me: bool, use_config_prefix: bool):
        self.need_reply_me = need_reply_me
        self.need_notice_me = need_notice_me
        self.use_config_prefix = use_config_prefix

    async def on_prepare(self, interface: Interface):
        if "$message_content" in interface.ctx:
            message: MessageChain = interface.ctx["$message_content"]
            is_reply_me = interface.ctx.get("is_reply_me", False)
            is_notice_me = interface.ctx.get("is_notice_me", False)
            if self.need_reply_me and not is_reply_me:
                return False
            if self.need_notice_me and not is_notice_me:
                return False
            if self.use_config_prefix and not (message := _remove_config_prefix(message)):
                return False
            return interface.update(**{"$message_content": message})
        return (await interface.query(MessageChain, "message", force_return=True)) is not None

    @property
    def before(self) -> set[str]:
        return {"entari.filter"}

    @property
    def after(self) -> set[str]:
        return {"entari.command/supplier"}

    @property
    def id(self) -> str:
        return "entari.command/message_judges"


class AlconnaSuppiler(BaseAuxiliary):
    cmd: Alconna

    def __init__(self, cmd: Alconna):
        self.cmd = cmd

    async def on_prepare(self, interface: Interface) -> Optional[Union[bool, Interface.Update]]:
        message = await interface.query(MessageChain, "message", force_return=True)
        if not message:
            return False
        session = await interface.query(Session, "session", force_return=True)
        with output_manager.capture(self.cmd.name) as cap:
            output_manager.set_action(lambda x: x, self.cmd.name)
            try:
                _res = self.cmd.parse(message)
            except Exception as e:
                _res = Arparma(self.cmd._hash, message, False, error_info=e)
            may_help_text: Optional[str] = cap.get("output", None)
        if _res.matched:
            return interface.update(alc_result=CommandResult(self.cmd, _res, may_help_text))
        elif may_help_text:
            if session:
                await session.send(MessageChain(may_help_text))
                return False
            return interface.update(alc_result=CommandResult(self.cmd, _res, may_help_text))
        return False

    @property
    def id(self) -> str:
        return "entari.command/supplier"


class AlconnaProvider(Provider[Any]):
    def __init__(self, type_: str, extra: Optional[dict] = None):
        super().__init__()
        self.type = type_
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


class Assign(BaseAuxiliary):
    def __init__(self, path: str, value: Any = _seminal, or_not: bool = False):
        self.path = path
        self.value = value
        self.or_not = or_not

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        result = await interface.query(CommandResult, "alc_result", force_return=True)
        if result is None:
            return False
        if self.value == _seminal:
            if self.path == "$main" or self.or_not:
                if not result.result.components:
                    return True
                return False
            return result.result.query(self.path, "\1") != "\1"
        else:
            if result.result.query(self.path) == self.value:
                return True
            if self.or_not and result.result.query(self.path) == Empty:
                return True
            return False

    @property
    def before(self) -> set[str]:
        return {"entari.command/supplier"}

    @property
    def id(self) -> str:
        return f"entari.command/assign:{self.path}"


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


def get_cmd(target: Subscriber):
    return next(a for a in target.auxiliaries["prepare"] if isinstance(a, AlconnaSuppiler)).cmd
