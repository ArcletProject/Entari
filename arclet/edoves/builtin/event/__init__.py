from arclet.edoves.main.event import EdovesBasicEvent

from .message import MessageReceived, MessageRevoked
from .network import DockerOperate
from .lifecycle import StartRunning, StopRunning
from .notice import NoticeMe, MonomerStatusUpdate, MonomerMetadataUpdate, RelationshipSetup, RelationshipSevered, \
    RelationshipTerminate
from ..medium import Request


class RequestReceived(EdovesBasicEvent):
    medium: Request
