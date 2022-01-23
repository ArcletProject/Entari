from ...main.event import BasicEvent
from ..medium import JsonMedium


class DockerOperate(BasicEvent):
    medium: JsonMedium
