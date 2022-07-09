from arclet.edoves.main.event import EdovesBasicEvent
from ..medium import Message


class MessageReceived(EdovesBasicEvent):
    medium: Message


class MessageRevoked(EdovesBasicEvent):
    medium: Message
