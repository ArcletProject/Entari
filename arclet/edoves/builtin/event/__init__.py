from ...main.event import EdovesBasicEvent
from ..medium import Request
from .message import MessageReceived, MessageRevoke
from .network import DockerOperate
from .lifecycle import StartRunning, StopRunning
from .notice import NoticeMe, MonomerStatusUpdate, MonomerMetadataUpdate, RelationshipSetup, RelationshipSevered, \
    RelationshipTerminate


class RequestReceived(EdovesBasicEvent):
    medium: Request
