from typing import cast

from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from arclet.edoves.main.utilles import IOStatus
from ...monomers import MahEntity
from ...protocol import MAHProtocol


class RelationshipOperateMeta(ParserMetadata):
    parser_targets = (
        "RelationshipRemove",
        "RelationshipGet",
        "MemberLeaveEventQuit",
        "MemberLeaveEventKick",
        "MemberJoinEvent",
    )


class RelationshipOperateBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        ev_type = self.io.metadata.select_type
        member_data = data.content.pop('member')
        group_data = member_data.pop('group')
        group = protocol.include_group(group_data)
        if 'MemberLeaveEvent' in ev_type:
            member = protocol.exclude_member(member_data, group_data.get("id"))
            if ev_type.endswith('Quit'):
                await protocol.post_notice(
                    "RelationshipTerminate",
                    member,
                    ev_type,
                    {"group": group},
                    relationship="Member"
                )
            elif ev_type.endswith('Kick'):
                operator_data = data.content.pop('operator')
                operator = protocol.include_member(operator_data)
                if not group.get_child(operator.metadata.pure_id):
                    group.set_child(group)
                operator.metadata.update_data("group_id", group.metadata.identifier)
                await protocol.post_notice(
                    "RelationshipSevered",
                    member,
                    ev_type,
                    {"group": group},
                    operator=operator,
                    relationship="Member"
                )
        else:
            member = protocol.include_member(member_data)
            if not group.get_child(member.metadata.pure_id):
                group.set_child(member)
            member.metadata.update_data("group_id", group.metadata.identifier)

            if ev_type.endswith('MemberJoinEvent'):
                await protocol.post_notice(
                    "RelationshipSetup",
                    member,
                    ev_type,
                    data.content,
                    relationship="Member"
                )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        action = self.io.metadata.select_type
        if action.endswith('Remove'):
            target = cast(MahEntity, data.content.get("target"))
            relationship = data.content.get("relationship")
            if relationship == "Member":
                group_id = target.metadata.group_id
                # 该群成员被移除
                target.get_parent(group_id).relation['children'].remove(target.metadata.identifier)
                # 该群成员与群组的关系解除
                target.relation['parents'].remove(f"{group_id}@{protocol.identifier}")
                if not target.compare('Friend') and not target.parents:
                    # 该群成员不是好友，且没有群组
                    protocol.scene.monomers.remove(target.metadata.pure_id)
                    target.metadata.state = IOStatus.DELETE_WAIT
                await protocol.docker.behavior.session_handle(
                    "post",
                    "kick",
                    {
                        "sessionKey": protocol.docker.metadata.session_key,
                        "target": group_id,
                        "memberId": target.metadata.pure_id
                    }
                )
        if action.endswith('Get'):
            relationship = data.content.get('relationship')
            _target: str = data.content.get("target")
            rest = data.content.get('rest')
            if relationship == "Member":
                group = cast(MahEntity, rest.get('group'))
                info = await protocol.docker.behavior.session_handle(
                    "get",
                    "memberInfo",
                    {
                        "sessionKey": protocol.docker.metadata.session_key,
                        "target": group.metadata.pure_id,
                        "memberId": _target
                    }
                )
                member = protocol.include_member(info)
                if not group.get_child(member.metadata.pure_id):
                    group.set_child(member)
                member.metadata.update_data("group_id", group.metadata.pure_id)
                data.send_response(member)
            if relationship == "Friend":
                profile = await protocol.docker.behavior.session_handle(
                    "get",
                    "friendProfile",
                    {"sessionKey": protocol.docker.metadata.session_key, "target": _target}
                )
                profile.setdefault("id", _target)
                friend = protocol.include_friend(profile)
                data.send_response(friend)


@MAHProtocol.register_parser
class RelationshipOperateParser(BaseDataParser):
    prefab_metadata = RelationshipOperateMeta
    prefab_behavior = RelationshipOperateBehavior
