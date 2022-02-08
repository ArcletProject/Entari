from typing import cast

from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
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
                if operator.metadata.identifier not in group.children:
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
            if member.metadata.identifier not in group.children:
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
                target.parents[group_id].children.pop(target.metadata.identifier)  # 该群成员被移除
                target.parents.pop(group_id)  # 该群成员与群组的关系解除
                if not target.compare('Friend') and not target.parents:  # 该群成员不是好友，且没有群组
                    protocol.scene.monomers.pop(target.metadata.identifier)
                await protocol.docker.behavior.session_handle(
                    "post",
                    "kick",
                    {
                        "sessionKey": protocol.docker.metadata.session_key,
                        "target": group_id,
                        "memberId": target.metadata.identifier
                    }
                )
        if action.endswith('Get'):
            relationship = data.content.get('relationship')
            target = cast(MahEntity, data.content.get("target"))
            rest = data.content.get('rest')
            if relationship == "Member":
                group = cast(MahEntity, rest.get('group'))
                info = await protocol.docker.behavior.session_handle(
                    "get",
                    "memberInfo",
                    {
                        "sessionKey": protocol.docker.metadata.session_key,
                        "target": group.metadata.identifier,
                        "memberId": target
                    }
                )
                member = protocol.include_member(info)
                if member.metadata.identifier not in group.children:
                    group.set_child(member)
                member.metadata.update_data("group_id", group.metadata.identifier)
                data.send_response(member)
            if relationship == "Friend":
                profile = await protocol.docker.behavior.session_handle(
                    "get",
                    "friendProfile",
                    {"sessionKey": protocol.docker.metadata.session_key, "target": target}
                )
                profile.setdefault("id", target)
                friend = protocol.include_friend(profile)
                data.send_response(friend)


@MAHProtocol.register_parser
class RelationshipOperateParser(BaseDataParser):
    prefab_metadata = RelationshipOperateMeta
    prefab_behavior = RelationshipOperateBehavior
