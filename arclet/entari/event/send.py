from dataclasses import dataclass
from typing import TYPE_CHECKING

from arclet.letoderea import Contexts, Result, define, provide
from satori.client import Account
from satori.model import MessageReceipt

from ..message import MessageChain

if TYPE_CHECKING:
    from ..session import Session


@dataclass
class SendRequest:
    account: Account
    channel: str
    message: MessageChain
    session: "Session | None" = None

    def check_result(self, value) -> Result[bool | MessageChain] | None:
        if isinstance(value, bool | MessageChain):
            return Result(value)


before_send_pub = define(SendRequest, name="entari.event/before_send")
before_send_pub.bind(provide(MessageChain, target="message"))


@before_send_pub.gather
async def req_gather(req: SendRequest, context: Contexts):
    context["account"] = req.account
    context["channel"] = req.channel
    context["message"] = req.message
    if req.session:
        context["session"] = req.session


@dataclass
class SendResponse:
    account: Account
    channel: str
    message: MessageChain
    result: list[MessageReceipt]
    session: "Session | None" = None


send_pub = define(SendResponse, name="entari.event/after_send")
send_pub.bind(provide(MessageChain, target="message"))
send_pub.bind(provide(list, target="result"))


@send_pub.gather
async def resp_gather(resp: SendResponse, context: Contexts):
    context["account"] = resp.account
    context["channel"] = resp.channel
    context["message"] = resp.message
    context["result"] = resp.result
    if resp.session:
        context["session"] = resp.session
