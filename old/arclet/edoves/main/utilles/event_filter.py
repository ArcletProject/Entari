from typing import Type

from arclet.letoderea.entities.auxiliary import BaseAuxiliary

from ..event import EdovesBasicEvent


class EventFilter(BaseAuxiliary):
    """用以对传入的事件进行预处理, 比如限定medium内容"""

    target_event: Type[EdovesBasicEvent]
    pass
