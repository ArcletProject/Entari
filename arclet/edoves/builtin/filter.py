from typing import List, Any

from ..utilles.event_filter import EventFilter, EdovesBasicEvent


class MonomerTagLimit(EventFilter):
    tags: List[str]

    def __init__(self, *monomer_tag: str):
        self.tags = list(monomer_tag)

    def judge(self, event: EdovesBasicEvent) -> bool:
        if len(self.tags) > 1:
            return event.medium.purveyor.compare(*self.tags)
        return event.medium.purveyor.prime_tag == self.tags[0]


class MonomerMetaLimit(EventFilter):
    path: List[str]

    def __init__(self, meta_name: str, value: Any):
        self.path = meta_name.split('.')
        if len(self.path) == 1:
            self.path.insert(0, '')
        self.value = value

    def judge(self, event: EdovesBasicEvent) -> bool:
        if self.path[0] == '':
            return event.medium.purveyor.__getattribute__(self.path[1]) == self.value
        if self.path[0] == 'metadata':
            return event.medium.purveyor.metadata.__getitem__(self.path[1]) == self.value
        if self.path[0] == 'behavior':
            return event.medium.purveyor.behavior.__getitem__(self.path[1]) == self.value
