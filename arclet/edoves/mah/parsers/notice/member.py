from typing import cast

from arclet.edoves.builtin.medium import DictMedium, Notice
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from ...protocol import MAHProtocol
from ...monomers import MahEntity


class MemberStatusMeta(ParserMetadata):
    parser_targets = (
        "MemberPermissionChangeEvent",
        "MemberMuteEvent",
        "MemberUnmuteEvent",
        "ChangeMonomerStatus"

    )


class MemberDataUpdateMeta(ParserMetadata):
    parser_targets = (
        "MemberCardChangeEvent",
        "MemberSpecialTitleChangeEvent",
        "MemberHonorChangeEvent"
    )


class MemberChangeStatusBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        member_data = data.content.pop('member')
        group_data = member_data.pop('group')
        group = protocol.include_monomer("group", group_data)

        member = protocol.include_monomer("member", member_data)
        if not group.get_child(member.metadata.pure_id):
            group.set_child(member)
        member.metadata.group_id = group.metadata.pure_id
        ev_type = self.io.metadata.select_type
        if ev_type == "MemberPermissionChangeEvent":
            notice = Notice().create(member, data.content, ev_type)
            await protocol.screen.push_medium(notice)
            await protocol.screen.broadcast_medium("MonomerStatusUpdate")
        else:
            operator_data = data.content.pop('operator')
            if not operator_data:
                operator = protocol.current_scene.protagonist
            else:
                operator = protocol.include_monomer("member", operator_data)
                if not group.get_child(operator.metadata.pure_id):
                    group.set_child(group)
                operator.metadata.group_id = group.metadata.pure_id
            notice = Notice().create(member, data.content, ev_type)
            notice.operator = operator
            await protocol.screen.push_medium(notice)
            await protocol.screen.broadcast_medium(
                "MonomerStatusUpdate", active=False, action=ev_type.replace('Member', '').replace('Event', '')
            )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        target = cast(MahEntity, data.content.get("target"))
        status = data.content.get("status")
        rest = data.content.get("rest")
        if status == "mute":
            is_mute = rest.get("mute")
            if target.prime_tag == "Member":
                if is_mute:
                    mute_time: int = rest.get("mute_time") or 60
                    await protocol.docker.behavior.session_handle(
                        "post",
                        "mute",
                        {
                            "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                            "target": target.metadata.group_id,
                            "memberId": target.metadata.pure_id,
                            "time": mute_time
                        }
                    )
                else:
                    await protocol.docker.behavior.session_handle(
                        "post",
                        "unmute",
                        {
                            "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                            "target": target.metadata.group_id,
                            "memberId": target.metadata.pure_id
                        }
                    )


class MemberChangeDataBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        member_data = data.content.pop('member')
        group_data = member_data.pop('group')
        group = protocol.include_monomer("group", group_data)

        member = protocol.include_monomer("member", member_data)
        if not group.get_child(member.metadata.pure_id):
            group.set_child(member)
        member.metadata.group_id = group.metadata.pure_id
        notice = Notice().create(member, data.content, self.io.metadata.select_type)
        await protocol.screen.push_medium(notice)
        await protocol.screen.broadcast_medium("MonomerMetadataUpdate")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        pass


@MAHProtocol.register_parser
class MemberStatusUpdateParser(BaseDataParser):
    prefab_metadata = MemberStatusMeta
    prefab_behavior = MemberChangeStatusBehavior


@MAHProtocol.register_parser
class MemberMetadataUpdateParser(BaseDataParser):
    prefab_metadata = MemberDataUpdateMeta
    prefab_behavior = MemberChangeDataBehavior
