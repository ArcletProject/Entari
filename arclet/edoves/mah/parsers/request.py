from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from ..protocol import MAHProtocol


class RequestOperateMeta(ParserMetadata):
    parser_targets = [
        "NewFriendRequestEvent",
        "MemberJoinRequestEvent",
        "BotInvitedJoinGroupRequestEvent",
        "Accept",
        "Reject",
    ]


class RequestOperateParserBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        friend = protocol.include_temporary_monomer(data.content.pop('nick'), data.content.pop('fromId'))
        await protocol.post_request(
            "RequestReceived",
            friend,
            self.io.metadata.select_type,
            data.content,
            str(data.content.pop("eventId"))
        )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        rtype = data.content.get('type')
        await protocol.docker.behavior.session_handle(
            "post",
            f"resp/{rtype[0].lower() + rtype[1:]}",
            {
                "sessionKey": protocol.docker.metadata.session_key,
                "eventId": data.content.get('eventId'),
                "fromId": data.content['content'].get('fromId'),
                "groupId": data.content['content'].get('groupId'),
                "operate": data.content.get('operate'),
                "message": data.content.get('msg')
            }
        )


@MAHProtocol.register_parser
class RequestEventParser(BaseDataParser):
    prefab_metadata = RequestOperateMeta
    prefab_behavior = RequestOperateParserBehavior
