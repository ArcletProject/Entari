from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

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
    __result_type__: "type[bool | None]" = Union[bool, None]


pub = es.define(SendRequest.__disp_name__, SendRequest)
pub.bind(provide(MessageChain, call=generate(deref(SendRequest).message)))
