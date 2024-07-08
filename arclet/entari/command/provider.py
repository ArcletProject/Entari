from copy import deepcopy
import inspect
from typing import Any, Literal, Optional, Union, get_args

from arclet.alconna import Alconna, Arparma, Duplication, Empty, output_manager
from arclet.alconna.builtin import generate_duplication
from arclet.letoderea import (
    Contexts,
    Interface,
    JudgeAuxiliary,
    Param,
    Provider,
    Scope,
    Subscriber,
    SupplyAuxiliary,
)
from arclet.letoderea.provider import ProviderFactory
from nepattern.util import CUnionType
from satori.client import Account
from satori.element import At, Text
from tarina.generic import get_origin

from ..message import MessageChain
from .model import CommandResult, Match, Query


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
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return "$message_content" in interface.ctx

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

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Union[bool, Interface.Update]]:
        account: Account = interface.ctx["$account"]
        message: MessageChain = interface.ctx["$message_content"]
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
            return interface.update(alc_result=CommandResult(self.cmd, _res, may_help_text))
        elif may_help_text:
            await account.send(interface.event, MessageChain(may_help_text))
            return False
        return False

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


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
    return next(a for a in target.auxiliaries[Scope.prepare] if isinstance(a, AlconnaSuppiler)).cmd
