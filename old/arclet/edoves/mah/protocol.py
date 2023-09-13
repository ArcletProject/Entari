from typing import Dict, Any, Literal, Optional, cast
from arclet.edoves.main.protocol import AbstractProtocol
from arclet.edoves.main.utilles import IOStatus
from arclet.edoves.main.medium import BaseMedium
from arclet.edoves.builtin.medium import Message
from arclet.edoves.main.utilles.data_source_info import DataSourceInfo
from .monomers import MahEntity
from .server_docker import MAHServerDocker


class MAHProtocol(AbstractProtocol):
    docker: MAHServerDocker
    regular_metas = ["permission", "specialTitle", "joinTimestamp", "lastSpeakTimestamp", "mutetimeRemaining"]
    regular_monomer = MahEntity

    def record_event(self, medium: BaseMedium, event: str):
        log_level: str = "INFO"
        group_message_log_format: str = (
            "{scene_name} >>> {bot_id}: [{group_name}({group_id})] {member_name}({member_id}) -> {message_string}")
        friend_message_log_format: str = "{scene_name} >>> {bot_id}: [{friend_name}({friend_id})] -> {message_string}"
        other_client_message_log_format: str = (
            "{scene_name} >>> {bot_id}: [{platform_name}({platform_id})] -> {message_string}")

        if self.current_scene.config.use_event_record:
            if event == "MessageReceived":
                medium: Message = cast(Message, medium)
                purveyor: MahEntity = cast(MahEntity, medium.purveyor)
                if medium.purveyor.prime_tag == "Member":
                    self.screen.edoves.logger.log(
                        log_level,
                        group_message_log_format.format(
                            scene_name=self.current_scene.scene_name,
                            group_name=purveyor.current_group.metadata.name,
                            group_id=purveyor.current_group.metadata.identifier,
                            member_id=purveyor.metadata.identifier,
                            member_name=purveyor.metadata.name,
                            bot_id=self.current_scene.protagonist.metadata.identifier,
                            message_string=medium.content.to_text().__repr__(),
                        ),
                    )
                elif medium.purveyor.prime_tag == "Friend":
                    self.screen.edoves.logger.log(
                        log_level,
                        friend_message_log_format.format(
                            scene_name=self.current_scene.scene_name,
                            friend_id=purveyor.metadata.identifier,
                            friend_name=purveyor.metadata.name,
                            bot_id=self.current_scene.protagonist.metadata.identifier,
                            message_string=medium.content.to_text().__repr__(),
                        ),
                    )

    async def put_metadata(self, meta: str, target: MahEntity, **kwargs):
        pass

    async def set_metadata(self, meta: str, value: Any, target: MahEntity, **kwargs):
        pass

    def include_temporary_monomer(self, name: str, identifier: str, alias: str = ""):
        friend = MahEntity(self, name, identifier, alias)
        friend.metadata.state = IOStatus.DELETE_WAIT
        friend.set_parent(self.current_scene.protagonist)
        return friend

    def include_monomer(
            self,
            mono_type: Literal["friend", "member", "group"],
            monomer_data: Optional[Dict[str, Any]] = None,
            target: Optional[str] = None,
            **kwargs
    ) -> MahEntity:
        mono_id = str(monomer_data.get('id'))
        mono_identifier = f"{mono_id}@{self.identifier}"
        if mono_type == 'friend':
            if not (friend := self.current_scene.monomer_map.get(mono_identifier)):
                friend = MahEntity(self, monomer_data.get("nickname"), mono_id, monomer_data.get("remark"))
                friend.set_parent(self.current_scene.protagonist)
                self.current_scene.monomers.append(mono_id)
            if friend.prime_tag == "Member":
                friend.set_parent(self.current_scene.protagonist)
                friend.metadata.name = monomer_data.get("nickname")
                friend.metadata.alias = monomer_data.get("remark")
            friend.set_prime_tag("Friend")
            return friend
        if mono_type == 'member':
            if not (member := self.current_scene.monomer_map.get(mono_identifier)):
                member = MahEntity(self, monomer_data.get("memberName"), mono_id)
                self.dispatch_metadata(member, monomer_data)
                self.current_scene.monomers.append(mono_id)
            elif member.prime_tag == "Member":
                member.metadata.name = monomer_data.get("memberName")
                self.dispatch_metadata(member, monomer_data)
            elif member.prime_tag == "Friend":
                member.metadata.alias = member.metadata.name
                member.metadata.name = monomer_data.get("memberName")
            member.set_prime_tag("Member")
            return member
        if mono_type == 'group':
            if not (group := self.current_scene.monomer_map.get(mono_identifier)):
                group = MahEntity(self, monomer_data.get("name"), mono_id)
                self.dispatch_metadata(group, monomer_data)
                self.current_scene.monomers.append(mono_id)
                group.set_child(self.current_scene.protagonist)
            else:
                group.metadata.name = monomer_data.get("name")
                self.dispatch_metadata(group, monomer_data)
            group.set_prime_tag("Group")
            return group

    def exclude_monomer(
            self,
            mono_type: Literal["friend", "member", "group"],
            monomer_data: Dict[str, Any],
            **kwargs
    ):
        mono_id = str(monomer_data.get('id'))
        mono_identifier = self.encode_unique_identifier(mono_id)
        if mono_type == 'friend':
            if not (friend := self.current_scene.monomer_map.get(mono_identifier)):
                friend = MahEntity(self, monomer_data.get("nickname"), mono_id, monomer_data.get("remark"))
            else:
                self.current_scene.protagonist.relation['children'].remove(friend.identifier)
                if not friend.compare("Member"):
                    friend.metadata.state = IOStatus.DELETE_WAIT
                    self.current_scene.monomers.remove(friend.metadata.identifier)
            friend.set_prime_tag("Friend")
            return friend
        if mono_type == 'member':
            if not (member := self.current_scene.monomer_map.get(mono_identifier)):
                member = MahEntity(self, monomer_data.get("memberName"), mono_id)
                self.dispatch_metadata(member, monomer_data)
            else:
                group_id = kwargs.get("group_id")
                member.get_parent(group_id).relation['children'].remove(member.identifier)
                member.relation['parents'].remove(self.encode_unique_identifier(group_id))
                if not member.compare('Friend') and not member.parents:
                    member.metadata.state = IOStatus.DELETE_WAIT
                    self.current_scene.monomers.remove(member.metadata.identifier)
            member.set_prime_tag("Member")
            return member
        if mono_type == 'group':
            if not (group := self.current_scene.monomer_map.get(mono_identifier)):
                group = MahEntity(self, monomer_data.get("name"), mono_id)
                self.dispatch_metadata(group, monomer_data)
            else:
                self.current_scene.monomers.remove(mono_id)
                self.current_scene.protagonist.relation['parents'].remove(mono_identifier)
                group.metadata.state = IOStatus.DELETE_WAIT

                for m in group.children:
                    # 群组与群组成员的关系解除
                    m.relation['parents'].remove(mono_identifier)
                    if len(m.parents) == 0:
                        # 群组成员与bot的所有关系解除
                        m.metadata.state = IOStatus.DELETE_WAIT
                        self.current_scene.monomers.remove(m.metadata.identifier)
                    elif m.compare("Friend") and len(m.parents) == 1:
                        m.remove_tags("Member")  # 群组成员与bot的群友关系解除
            group.set_prime_tag("Group")
            return group

    def event_type_predicate(self, content) -> str:
        return content.get('type')

    async def ensure_self(self):
        profile = await self.docker.behavior.session_handle(
            "get",
            "botProfile",
            {"sessionKey": self.docker.metadata.session_keys[self.current_scene.scene_name]}
        )
        self.current_scene.protagonist.metadata.name = profile.get("nickname")

    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="Default"
    )
