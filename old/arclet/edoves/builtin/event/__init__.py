from arclet.edoves.main.event import EdovesBasicEvent

from ..medium import Request
from .lifecycle import StartRunning, StopRunning
from .message import MessageReceived, MessageRevoked
from .network import DockerOperate
from .notice import (
    MonomerMetadataUpdate,
    MonomerStatusUpdate,
    NoticeMe,
    RelationshipSetup,
    RelationshipSevered,
    RelationshipTerminate,
)


class RequestReceived(EdovesBasicEvent):
    medium: Request
