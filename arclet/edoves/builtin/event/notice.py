from ...main.event import EdovesBasicEvent
from ..medium import Notice


class NoticeMe(EdovesBasicEvent):
    medium: Notice


class MonomerMetadataUpdate(EdovesBasicEvent):
    action: str
    medium: Notice


class RelationshipSolution(EdovesBasicEvent):
    medium: Notice


class RelationshipDissolution(EdovesBasicEvent):
    medium: Notice
