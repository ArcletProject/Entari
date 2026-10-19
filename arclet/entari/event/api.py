from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from arclet.letoderea import Contexts, Result, define, provide
from satori import ChannelType
from satori.client import Account
from satori.exception import ActionFailed
from satori.model import Channel, MessageObject

from ..const import ITEM_ACCOUNT, ITEM_CHANNEL, ITEM_MESSAGE_CONTENT, ITEM_SESSION
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


@before_send_pub.gather
async def send_req_gather(req: SendRequest, context: Contexts):
    context[ITEM_ACCOUNT] = req.account
    context[ITEM_MESSAGE_CONTENT] = req.message
    if req.session:
        context[ITEM_SESSION] = req.session
        context[ITEM_CHANNEL] = req.session.channel
    else:
        try:
            context[ITEM_CHANNEL] = await req.account.channel_get(req.channel)
        except ActionFailed:
            context[ITEM_CHANNEL] = Channel(
                req.channel, ChannelType.DIRECT if req.channel.startswith("private:") else ChannelType.TEXT
            )


@dataclass
class SendResponse:
    account: Account
    channel: str
    message: MessageChain
    result: list[MessageObject]
    session: "Session | None" = None


send_pub = define(SendResponse, name="entari.event/after_send")
send_pub.providers.append(provide(list[MessageObject], call="$resp_result"))


@send_pub.gather
async def send_resp_gather(resp: SendResponse, context: Contexts):
    context[ITEM_ACCOUNT] = resp.account
    context[ITEM_MESSAGE_CONTENT] = resp.message
    context["$resp_result"] = resp.result
    if resp.session:
        context[ITEM_SESSION] = resp.session
        context[ITEM_CHANNEL] = resp.session.channel
    else:
        try:
            context[ITEM_CHANNEL] = await resp.account.channel_get(resp.channel)
        except ActionFailed:
            context[ITEM_CHANNEL] = Channel(
                resp.channel, ChannelType.DIRECT if resp.channel.startswith("private:") else ChannelType.TEXT
            )


@dataclass
class APIRequest:
    account: Account
    name: str
    params: dict[str, Any]


before_api_pub = define(APIRequest, name="entari.event/before_api_call")


@before_api_pub.gather
async def call_req_gather(req: APIRequest, context: Contexts):
    context[ITEM_ACCOUNT] = req.account


@dataclass
class APIResponse:
    account: Account
    name: str
    params: dict[str, Any]
    success: bool
    result: Any


after_api_pub = define(APIResponse, name="entari.event/after_api_call")


@after_api_pub.gather
async def call_resp_gather(resp: APIResponse, context: Contexts):
    context[ITEM_ACCOUNT] = resp.account
