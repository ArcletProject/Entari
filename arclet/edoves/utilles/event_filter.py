from arclet.letoderea.entities.condition import EventCondition, abstractmethod
from ..main.event import EdovesBasicEvent


class EventFilter(EventCondition):
    """用以对传入的事件进行预处理, 比如限定medium内容"""

    @abstractmethod
    def judge(self, event: EdovesBasicEvent) -> bool:
        ...
