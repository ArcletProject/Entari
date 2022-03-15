from typing import Dict, Any, List, Optional
from arclet.edoves.main.protocol import AbstractProtocol
from arclet.edoves.main.utilles import IOStatus
from arclet.edoves.main.utilles.data_source_info import DataSourceInfo
from arclet.edoves.builtin.medium import Message, Notice, Request
from .monomers import MahEntity
from .chain import MessageChain
from .server_docker import MAHServerDocker


class MAHProtocol(AbstractProtocol):

    def event_type_predicate(self, content) -> str:
        return content.get('type')

    docker_type = MAHServerDocker
    docker: MAHServerDocker

    def include_temporary_monomer(self, name: str, identifier: str, alias: str = ""):
        friend = MahEntity(
            self.scene.protocol,
            name,
            identifier,
            alias
        )
        friend.metadata.state = IOStatus.DELETE_WAIT
        friend.set_parent(self.scene.protagonist)
        return friend

    def include_friend(self, friend_data: Dict[str, Any]):
        friend_id = str(friend_data.get('id'))
        if not (friend := self.scene.monomer_map.get(f"{friend_id}@{self.identifier}")):
            friend = MahEntity(
                self.scene.protocol,
                friend_data.get("nickname"),
                friend_id,
                friend_data.get("remark")
            )
            friend.set_parent(self.scene.protagonist)
            self.scene.monomers.append(friend_id)
        if friend.prime_tag == "Member":
            friend.set_parent(self.scene.protagonist)
            friend.metadata.update_data("name", friend_data.get("nickname"))
            friend.metadata.update_data("alias", friend_data.get("remark"))
        friend.set_prime_tag("Friend")
        return friend

    def exclude_friend(self, friend_data: Dict[str, Any]):
        friend_id = str(friend_data.get('id'))
        if not (friend := self.scene.monomer_map.get(f"{friend_id}@{self.identifier}")):
            friend = MahEntity(
                self.scene.protocol,
                friend_data.get("nickname"),
                friend_id,
                friend_data.get("remark")
            )
        else:
            self.scene.protagonist.children.pop(friend.metadata.identifier)
            if not friend.compare("Member"):
                friend.metadata.state = IOStatus.DELETE_WAIT
                self.scene.monomers.remove(friend.metadata.pure_id)
        friend.set_prime_tag("Friend")
        return friend

    def include_member(self, member_data: Dict[str, Any]):
        member_id = str(member_data.get('id'))
        if not (member := self.scene.monomer_map.get(f"{member_id}@{self.identifier}")):
            member = MahEntity(
                self.scene.protocol,
                member_data.get("memberName"),
                member_id,
                **{
                    "permission": member_data.get("permission"),
                    "specialTitle": member_data.get("specialTitle"),
                    "joinTimestamp": member_data.get("joinTimestamp"),
                    "lastSpeakTimestamp": member_data.get("lastSpeakTimestamp"),
                    "muteTimeRemaining": member_data.get("muteTimeRemaining"),
                }
            )
            self.scene.monomers.append(member_id)
        elif member.prime_tag == "Member":
            member.metadata.update_data("name", member_data.get("memberName"))
            member.metadata.update_data("permission", member_data.get("permission"))
            member.metadata.update_data("specialTitle", member_data.get("specialTitle"))
            member.metadata.update_data("joinTimestamp", member_data.get("joinTimestamp"))
            member.metadata.update_data("lastSpeakTimestamp", member_data.get("lastSpeakTimestamp"))
            member.metadata.update_data("muteTimeRemaining", member_data.get("muteTimeRemaining"))
        elif member.prime_tag == "Friend":
            member.metadata.alias = member.metadata.name
            member.metadata.update_data("name", member_data.get("memberName"))
        member.set_prime_tag("Member")
        return member

    def exclude_member(self, member_data: Dict[str, Any], group_id: str):
        member_id = str(member_data.get('id'))
        if not (member := self.scene.monomer_map.get(f"{member_id}@{self.identifier}")):
            member = MahEntity(
                self.scene.protocol,
                member_data.get("memberName"),
                member_id,
                **{
                    "permission": member_data.get("permission"),
                    "specialTitle": member_data.get("specialTitle"),
                    "joinTimestamp": member_data.get("joinTimestamp"),
                    "lastSpeakTimestamp": member_data.get("lastSpeakTimestamp"),
                    "muteTimeRemaining": member_data.get("muteTimeRemaining"),
                }
            )
        else:
            member.get_parent(group_id).relation['children'].remove(member.metadata.identifier)
            member.relation['parents'].remove(f"{group_id}@{self.identifier}")
            if not member.compare('Friend') and not member.parents:
                member.metadata.state = IOStatus.DELETE_WAIT
                self.scene.monomers.remove(member.metadata.pure_id)
        member.set_prime_tag("Member")
        return member

    def include_group(self, group_data: Dict[str, Any]):
        group_id = str(group_data.get('id'))
        if not (group := self.scene.monomer_map.get(f"{group_id}@{self.identifier}")):
            group = MahEntity(
                self.scene.protocol,
                group_data.get("name"),
                group_id,
                **{
                    "permission": group_data.get("permission"),
                }
            )
            self.scene.monomers.append(group_id)
            group.set_child(self.scene.protagonist)
        else:
            group.metadata.update_data("name", group_data.get("name"))
            group.metadata.update_data("permission", group_data.get("permission"))
        group.set_prime_tag("Group")
        return group

    def exclude_group(self, group_data: Dict[str, Any]):
        group_id = str(group_data.get('id'))
        if not (group := self.scene.monomer_map.get(f"{group_id}@{self.identifier}")):
            group = MahEntity(
                self.scene.protocol,
                group_data.get("name"),
                group_id,
                **{
                    "permission": group_data.get("permission"),
                }
            )
        else:
            self.scene.monomers.remove(group_id)
            self.scene.protagonist.relation['parents'].remove(f"{group_id}@{self.identifier}")
            group.metadata.state = IOStatus.DELETE_WAIT

            for m in group.children:
                # 群组与群组成员的关系解除
                m.relation['parents'].remove(f"{group_id}@{self.identifier}")
                if len(m.parents) == 0:
                    # 群组成员与bot的所有关系解除
                    m.metadata.state = IOStatus.DELETE_WAIT
                    self.scene.monomers.remove(m.metadata.pure_id)
                elif m.compare("Friend") and len(m.parents) == 1:
                    m.remove_tags("Member")  # 群组成员与bot的群友关系解除
        group.set_prime_tag("Group")
        return group

    async def post_message(
            self,
            ev_type: str,
            purveyor: MahEntity,
            medium_type: str,
            content: List[Dict[str, str]],
            **kwargs
    ):
        msg = Message().create(purveyor, MessageChain.parse_obj(content), medium_type)
        msg.id = str(msg.content.find("Source").id)
        msg.time = msg.content.find("Source").time
        msg.content.remove("Source")
        await self.push_medium(msg)
        await self.broadcast_medium(ev_type, **kwargs)

    async def post_notice(
            self,
            ev_type: str,
            purveyor: MahEntity,
            medium_type: str,
            content: Dict[str, Any],
            operator: Optional[MahEntity] = None,
            **kwargs
    ):
        notice = Notice().create(purveyor, content, medium_type)
        if operator:
            notice.operator = operator
        await self.push_medium(notice)
        await self.broadcast_medium(ev_type, **kwargs)

    async def post_request(
            self,
            ev_type: str,
            purveyor: MahEntity,
            medium_type: str,
            content: Dict[str, str],
            event_id: str,
            **kwargs
    ):
        request = Request().create(purveyor, content, medium_type, event=event_id)
        await self.push_medium(request)
        await self.broadcast_medium(ev_type, **kwargs)

    async def ensure_self(self):
        profile = await self.docker.behavior.session_handle(
            "get",
            "botProfile",
            {"sessionKey": self.docker.metadata.session_key}
        )
        self.scene.protagonist.metadata.name = profile.get("nickname")

    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="Default"
    )
    medium_type = Dict
