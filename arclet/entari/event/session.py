from dataclasses import dataclass
from typing import TYPE_CHECKING

from arclet.letoderea import deref, es, provide
from arclet.letoderea.ref import generate

from ..message import MessageChain
from .base import BasedEvent

if TYPE_CHECKING:
    from ..session import Session


@dataclass
class SendRequest(BasedEvent):
    session: "Session"
    message: "MessageChain"

    __disp_name__ = "entari.event/before_send"


pub = es.define("entari.event/before_send", SendRequest, lambda x: {"session": x.session, "message": x.message})
pub.bind(provide(MessageChain, call=generate(deref(SendRequest).message)))
