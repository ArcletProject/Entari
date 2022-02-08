from ...main.event import EdovesBasicEvent
from ..medium import DictMedium


class DockerOperate(EdovesBasicEvent):
    medium: DictMedium


class DockerStart(EdovesBasicEvent):
    medium: DictMedium
