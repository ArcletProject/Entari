from typing import cast

from arclet.edoves.main.interact import IOManager
from arclet.edoves.builtin.medium import DictMedium, Notice
from arclet.edoves.main.interact.parser import BaseDataParser, ParserBehavior, ParserMetadata
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
        group = protocol.include_monomer("group", group_data)
        if 'MemberLeaveEvent' in ev_type:
            member = protocol.exclude_monomer("member", member_data, group_id=group_data.get("id"))
            if ev_type.endswith('Quit'):
                notice = Notice().create(member, {"group": group}, ev_type)
                await protocol.screen.push(notice)
                await protocol.screen.broadcast("RelationshipTerminate", relationship="Member")
            elif ev_type.endswith('Kick'):
                operator_data = data.content.pop('operator')
                operator = protocol.include_monomer("member", operator_data)
                if not group.get_child(operator.metadata.identifier):
                    group.set_child(group)
                operator.metadata.group_id = group.metadata.identifier
                notice = Notice().create(member, {"group": group}, ev_type)
                notice.operator = operator
                await protocol.screen.push(notice)
                await protocol.screen.broadcast("RelationshipSevered", relationship="Member")
        else:
            member = protocol.include_monomer("member", member_data)
            if not group.get_child(member.metadata.identifier):
                group.set_child(member)
            member.metadata.group_id = group.metadata.identifier

            if ev_type.endswith('MemberJoinEvent'):
                notice = Notice().create(member, data.content, ev_type)
                await protocol.screen.push(notice)
                await protocol.screen.broadcast("RelationshipSetup", relationship="Member")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        action = self.io.metadata.select_type
        if action.endswith('Remove'):
            target = cast(MahEntity, data.content.get("target"))
            relationship = data.content.get("relationship")
            if relationship == "Member":
                group_id = target.metadata.group_id
                # 该群成员被移除
                target.get_parent(group_id).relation['children'].remove(target.identifier)
                # 该群成员与群组的关系解除
                target.relation['parents'].remove(protocol.encode_unique_identifier(group_id))
                if not target.compare('Friend') and not target.parents:
                    # 该群成员不是好友，且没有群组
                    protocol.current_scene.monomers.remove(target.metadata.identifier)
                    target.metadata.state = IOStatus.DELETE_WAIT
                await protocol.docker.behavior.session_handle(
                    "post",
                    "kick",
                    {
                        "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                        "target": group_id,
                        "memberId": target.metadata.identifier
                    }
                )
        if action.endswith('Get'):
            relationship = data.content.get('relationship')
            _target: str = data.content.get("target")
            rest = data.content.get('rest')
            list_all = rest.get('list_all')
            if relationship == "Member":
                if list_all:
                    member_list = await protocol.docker.behavior.session_handle(
                        "get",
                        "memberList",
                        {
                            "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                            "target": _target,
                        }
                    )
                    res = []
                    for _member_data in member_list:
                        if str(_member_data.get("id")) not in protocol.current_scene.monomers:
                            _member = protocol.include_monomer("member", _member_data)
                            protocol.current_scene.monomers.remove(str(_member_data.get("id")))
                            del IOManager.storage[_member.identifier]
                            _member.metadata.group_id = _member_data['group']['id']
                        else:
                            _member = protocol.current_scene.monomer_map.get(
                                protocol.encode_unique_identifier(_member_data.get("id"))
                            )
                            if _member.prime_tag == "Friend":
                                _member.metadata.alias = _member.metadata.name
                                _member.metadata.name = _member_data.get("memberName")
                                _member.set_prime_tag("Member")
                        res.append(_member)
                    data.send_response(res)
                else:
                    group = rest.get('group')
                    info = await protocol.docker.behavior.session_handle(
                        "get",
                        "memberInfo",
                        {
                            "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                            "target": group.metadata.identifier if isinstance(group, MahEntity) else group,
                            "memberId": _target
                        }
                    )
                    if not isinstance(group, MahEntity):
                        group = protocol.include_monomer("group", info.get("group"))
                    member = protocol.include_monomer("member", info)
                    if not group.get_child(member.metadata.identifier):
                        group.set_child(member)
                    member.metadata.group_id = group.metadata.identifier
                    data.send_response(member)
            if relationship == "Friend":
                if list_all:
                    friend_list = await protocol.docker.behavior.session_handle(
                        "get",
                        "friendList",
                        {"sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name]}
                    )
                    res = []
                    for _friend_data in friend_list:
                        if str(_friend_data.get("id")) not in protocol.current_scene.monomers:
                            _friend = protocol.include_monomer("friend", _friend_data)
                            protocol.current_scene.monomers.remove(str(_friend_data.get("id")))
                            del IOManager.storage[_friend.identifier]
                        else:
                            _friend = protocol.current_scene.monomer_map.get(
                                protocol.encode_unique_identifier(_friend_data.get("id"))
                            )
                            if _friend.prime_tag == "Member":
                                _friend.set_parent(protocol.current_scene.protagonist)
                                _friend.metadata.name = _friend_data.get("nickname")
                                _friend.metadata.alias = _friend_data.get("remark")
                                _friend.set_prime_tag("Friend")
                        res.append(_friend)
                    data.send_response(res)
                    return
                if rest.get('detail', False):
                    friend_list = await protocol.docker.behavior.session_handle(
                        "get",
                        "friendList",
                        {"sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name]}
                    )
                    for frid in friend_list:
                        if str(frid.get("id")) == _target:
                            friend = protocol.include_monomer("friend", frid)
                            data.send_response(friend)
                            return
                else:
                    profile = await protocol.docker.behavior.session_handle(
                        "get",
                        "friendProfile",
                        {
                            "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                            "target": _target
                        }
                    )
                    profile.setdefault("id", _target)
                    friend = protocol.include_monomer("friend", profile)
                    data.send_response(friend)
            if relationship == "Group":
                group_list = await protocol.docker.behavior.session_handle(
                    "get",
                    "groupList",
                    {"sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name]}
                )
                if list_all:
                    res = []
                    for _group_data in group_list:
                        if str(_group_data.get("id")) not in protocol.current_scene.monomers:
                            _group = protocol.include_monomer("group", _group_data)
                            protocol.current_scene.monomers.remove(str(_group_data.get("id")))
                            del IOManager.storage[_group.identifier]
                        else:
                            _group = protocol.current_scene.monomer_map.get(
                                protocol.encode_unique_identifier(_group_data.get("id"))
                            )
                            _group.metadata.name = _group_data.get("name")
                            _group.metadata.permission = _group_data.get("permission")
                        res.append(_group)
                    data.send_response(res)
                    return
                for _group in group_list:
                    if str(_group.get("id")) == _target:
                        group = protocol.include_monomer("group", _group)
                        data.send_response(group)
                        return


@MAHProtocol.register_parser
class RelationshipOperateParser(BaseDataParser):
    prefab_metadata = RelationshipOperateMeta
    prefab_behavior = RelationshipOperateBehavior
