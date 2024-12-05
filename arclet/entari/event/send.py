from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from arclet.letoderea import Contexts, es, provide
from satori.client import Account
from satori.model import MessageReceipt

from ..message import MessageChain
from .base import BasedEvent

if TYPE_CHECKING:
    from ..session import Session


@dataclass
class SendRequest(BasedEvent):
    account: Account
    channel: str
    message: MessageChain
    session: Union["Session", None] = None

    async def gather(self, context: Contexts):
        context["account"] = self.account
        context["channel"] = self.channel
        context["message"] = self.message
        if self.session:
            context["session"] = self.session

    __publisher__ = "entari.event/before_send"
    __result_type__: "type[bool | MessageChain]" = Union[bool, MessageChain]


before_send_pub = es.define(SendRequest.__publisher__, SendRequest)
before_send_pub.bind(provide(MessageChain, target="message"))


@dataclass
class SendResponse(BasedEvent):
    account: Account
    channel: str
    message: MessageChain
    result: list[MessageReceipt]
    session: Union["Session", None] = None

    async def gather(self, context: Contexts):
        context["account"] = self.account
        context["channel"] = self.channel
        context["message"] = self.message
        context["result"] = self.result
        if self.session:
            context["session"] = self.session

    __publisher__ = "entari.event/send"


send_pub = es.define(SendResponse.__publisher__, SendResponse)
send_pub.bind(provide(MessageChain, target="message"))
send_pub.bind(provide(list, target="result"))
