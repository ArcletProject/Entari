from typing import cast

from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from ...protocol import MAHProtocol
from ...monomers import MahEntity


class GroupStatusMeta(ParserMetadata):
    parser_targets = (
        "GroupAllowConfessTalkEvent",
        "GroupMuteAllEvent",
        "GroupAllowAnonymousChatEvent",
        "GroupAllowMemberInviteEvent",
        "ChangeMonomerStatus"
    )


class GroupDataUpdateMeta(ParserMetadata):
    parser_targets = (
        "GroupNameChangeEvent",
        "GroupEntranceAnnouncementChangeEvent",
    )


class GroupChangeStatusBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        group_data = data.content.pop('group')
        group = protocol.include_group(group_data)
        ev_type = self.io.metadata.select_type
        if ev_type == "GroupAllowConfessTalkEvent":
            await protocol.post_notice(
                "MonomerStatusUpdate",
                group,
                ev_type,
                data.content,
                action="AllowConfessTalk"
            )
        else:
            operator_data = data.content.pop('operator')
            operator = protocol.include_member(operator_data)
            if not group.get_child(operator.metadata.pure_id):
                group.set_child(group)
            operator.metadata.update_data("group_id", group.metadata.pure_id)
            await protocol.post_notice(
                "MonomerStatusUpdate",
                group,
                ev_type,
                data.content,
                operator=operator
            )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        target = cast(MahEntity, data.content.get("target"))
        status = data.content.get("status")
        rest = data.content.get("rest")
        if status == "mute" and target.prime_tag == "Group":
            is_mute = rest.get("mute")
            if is_mute:
                await protocol.docker.behavior.session_handle(
                    "post",
                    "muteAll",
                    {
                        "sessionKey": protocol.docker.metadata.session_key,
                        "target": target.metadata.pure_id
                    }
                )
            else:
                await protocol.docker.behavior.session_handle(
                    "post",
                    "unmuteAll",
                    {
                        "sessionKey": protocol.docker.metadata.session_key,
                        "target": target.metadata.pure_id
                    }
                )


class GroupChangeDataBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        group_data = data.content.pop('group')
        group = protocol.include_group(group_data)
        operator_data = data.content.pop('operator')
        operator = protocol.include_member(operator_data)
        if not group.get_child(operator.metadata.pure_id):
            group.set_child(group)
        operator.metadata.update_data("group_id", group.metadata.pure_id)
        await protocol.post_notice(
            "MonomerMetadataUpdate",
            group,
            self.io.metadata.select_type,
            data.content,
            operator=operator
        )

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
