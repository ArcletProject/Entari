from arclet.edoves.builtin.medium import DictMedium, Notice
from arclet.edoves.main.interact.parser import BaseDataParser, ParserBehavior, ParserMetadata
from ...protocol import MAHProtocol


class FriendEventMeta(ParserMetadata):
    parser_targets = (
        "FriendInputStatusChangedEvent",
        "FriendNickChangedEvent"
    )


class FriendEventBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        friend = protocol.include_monomer("friend", data.content.pop('friend'))
        notice = Notice().create(friend, data.content, self.io.metadata.select_type)
        await protocol.screen.push_medium(notice)
        await protocol.screen.broadcast_medium("MonomerMetadataUpdate")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        pass


@MAHProtocol.register_parser
class FriendEventParser(BaseDataParser):
    prefab_metadata = FriendEventMeta
    prefab_behavior = FriendEventBehavior
