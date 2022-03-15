from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from ...protocol import MAHProtocol


class FriendEventMeta(ParserMetadata):
    parser_targets = (
        "FriendInputStatusChangedEvent",
        "FriendNickChangedEvent"
    )


class FriendEventBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        friend = protocol.include_friend(data.content.pop('friend'))
        await protocol.post_notice(
            "MonomerMetadataUpdate",
            friend,
            self.io.metadata.select_type,
            data.content
        )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        pass


@MAHProtocol.register_parser
class FriendEventParser(BaseDataParser):
    prefab_metadata = FriendEventMeta
    prefab_behavior = FriendEventBehavior
