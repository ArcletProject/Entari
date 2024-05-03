from typing import cast

from arclet.edoves.builtin.medium import DictMedium, Notice
from arclet.edoves.main.interact.parser import BaseDataParser, ParserBehavior, ParserMetadata

from ...monomers import MahEntity
from ...protocol import MAHProtocol


class GroupStatusMeta(ParserMetadata):
    parser_targets = (
        "GroupAllowConfessTalkEvent",
        "GroupMuteAllEvent",
        "GroupAllowAnonymousChatEvent",
        "GroupAllowMemberInviteEvent",
        "ChangeMonomerStatus",
    )


class GroupDataUpdateMeta(ParserMetadata):
    parser_targets = (
        "GroupNameChangeEvent",
        "GroupEntranceAnnouncementChangeEvent",
    )


class GroupChangeStatusBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        group = protocol.include_monomer("group", data.content.pop("group"))
        ev_type = self.io.metadata.select_type
        if ev_type == "GroupAllowConfessTalkEvent":
            notice = Notice().create(group, data.content, ev_type)
            await protocol.screen.push(notice)
            await protocol.screen.broadcast("MonomerStatusUpdate", action="AllowConfessTalk")
        else:
            operator_data = data.content.pop("operator")
            operator = protocol.include_monomer("member", operator_data)
            if not group.get_child(operator.metadata.identifier):
                group.set_child(group)
            operator.metadata.group_id = group.metadata.identifier
            notice = Notice().create(group, data.content, ev_type)
            notice.operator = operator
            await protocol.screen.push(notice)
            await protocol.screen.broadcast("MonomerStatusUpdate")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        target = cast(MahEntity, data.content.get("target"))
        rest = data.content.get("rest")
        if data.content.get("status") == "mute" and target.prime_tag == "Group":
            if rest.get("mute"):
                await protocol.docker.behavior.session_handle(
                    "post",
                    "muteAll",
                    {
                        "sessionKey": protocol.docker.metadata.session_keys[
                            protocol.current_scene.scene_name
                        ],
                        "target": target.metadata.identifier,
                    },
                )
            else:
                await protocol.docker.behavior.session_handle(
                    "post",
                    "unmuteAll",
                    {
                        "sessionKey": protocol.docker.metadata.session_keys[
                            protocol.current_scene.scene_name
                        ],
                        "target": target.metadata.identifier,
                    },
                )


class GroupChangeDataBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        group_data = data.content.pop("group")
        group = protocol.include_monomer("group", group_data)
        operator_data = data.content.pop("operator")
        operator = protocol.include_monomer("member", operator_data)
        if not group.get_child(operator.metadata.identifier):
            group.set_child(group)
        operator.metadata.group_id = group.metadata.identifier
        notice = Notice().create(group, data.content, self.io.metadata.select_type)
        notice.operator = operator
        await protocol.screen.push(notice)
        await protocol.screen.broadcast("MonomerMetadataUpdate")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        pass


@MAHProtocol.register_parser
class GroupStatusUpdateParser(BaseDataParser):
    prefab_metadata = GroupStatusMeta
    prefab_behavior = GroupChangeStatusBehavior


@MAHProtocol.register_parser
class GroupMetadataUpdateParser(BaseDataParser):
    prefab_metadata = GroupDataUpdateMeta
    prefab_behavior = GroupChangeDataBehavior
