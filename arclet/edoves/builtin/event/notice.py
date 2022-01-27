from ...main.event import EdovesBasicEvent
from ..medium import Notice


class NoticeSelf(EdovesBasicEvent):
    medium: Notice


class MonomerStatusChanged(EdovesBasicEvent):
    action: str
    medium: Notice


class MonomerMetadataChanged(EdovesBasicEvent):
    action: str
    medium: Notice


class RelationCreate(EdovesBasicEvent):
    medium: Notice


class RelationDestroy(EdovesBasicEvent):
    medium: Notice
