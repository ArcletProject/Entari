from ...main.event import BasicEvent
from ..medium import Message


class AllMessage(BasicEvent):
    medium: Message
