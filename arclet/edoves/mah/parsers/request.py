from arclet.edoves.builtin.medium import DictMedium, Request
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
        request = Request().create(
            friend, data.content, self.io.metadata.select_type, event=str(data.content.pop("eventId"))
        )
        await protocol.screen.push_medium(request)
        await protocol.screen.broadcast_medium("RequestReceived")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        rtype = data.content.get('type')
        await protocol.docker.behavior.session_handle(
            "post",
            f"resp/{rtype[0].lower() + rtype[1:]}",
            {
                "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
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
