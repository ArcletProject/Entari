from typing import List, Any

from arclet.edoves.main.utilles.event_filter import EventFilter, EdovesBasicEvent


class MediumTypeLimit(EventFilter):
    mtype: str

    def __init__(self, type: str):
        self.mtype = type
        super().__init__()

        @self.set_aux("before_parse", "judge")
        def judge(sf: MediumTypeLimit, event: EdovesBasicEvent) -> bool:
            return any([event.medium.type == sf.mtype, event.__class__.__name__ == sf.mtype])


class MonomerTagLimit(EventFilter):
    tags: List[str]

    def __init__(self, *monomer_tag: str):
        self.tags = list(monomer_tag)
        super().__init__()

        @self.set_aux("before_parse", "judge")
        def judge(sf: MonomerTagLimit, event: EdovesBasicEvent) -> bool:
            if len(sf.tags) > 1:
                return event.medium.purveyor.compare(*sf.tags)
            return event.medium.purveyor.prime_tag == sf.tags[0]


class MonomerMetaLimit(EventFilter):
    path: List[str]

    def __init__(self, meta_name: str, value: Any):
        self.path = meta_name.split('.')
        if len(self.path) == 1:
            self.path.insert(0, '')
        self.value = value
        super().__init__()

        @self.set_aux("before_parse", "judge")
        def judge(sf: MonomerMetaLimit, event: EdovesBasicEvent) -> bool:
            if sf.path[0] == '':
                return event.medium.purveyor.__getattribute__(sf.path[1]) == sf.value
            if sf.path[0] == 'metadata':
                return event.medium.purveyor.metadata.__getitem__(sf.path[1]) == sf.value
            if sf.path[0] == 'behavior':
                return event.medium.purveyor.behavior.__getitem__(sf.path[1]) == sf.value
