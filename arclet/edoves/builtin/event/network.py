from ...main.event import EdovesBasicEvent
from ..medium import JsonMedium


class DockerOperate(EdovesBasicEvent):
    medium: JsonMedium


class DockerStart(EdovesBasicEvent):
    medium: JsonMedium
