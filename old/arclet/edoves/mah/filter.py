from typing import Union, List
from arclet.edoves.builtin.filter import MonomerTagLimit, EdovesBasicEvent
from .monomers import MEMetadata


class FriendLimit(MonomerTagLimit):
    ids: List[str]

    def __init__(self, *identifier: Union[str, int]):
        super(FriendLimit, self).__init__("Friend")
        self.ids = [str(i) for i in identifier]

        @self.set_aux("before_parse", "judge")
        def judge(sf: FriendLimit, event: EdovesBasicEvent) -> bool:
            if sf.ids:
                return event.medium.purveyor.prime_tag == sf.tags[0] \
                       and event.medium.purveyor.metadata.identifier in sf.ids
            return event.medium.purveyor.prime_tag == sf.tags[0]


class GroupLimit(MonomerTagLimit):
    ids: List[str]

    def __init__(self, *identifier: Union[str, int]):
        super(GroupLimit, self).__init__("Member")
        self.ids = [str(i) for i in identifier]

        @self.set_aux("before_parse", "judge")
        def judge(sf: GroupLimit, event: EdovesBasicEvent) -> bool:
            if sf.ids:
                return event.medium.purveyor.prime_tag == sf.tags[0] \
                       and event.medium.purveyor.get_component(MEMetadata).group_id in sf.ids
            return event.medium.purveyor.prime_tag == sf.tags[0]
