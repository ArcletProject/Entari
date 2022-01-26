from typing import Dict, TYPE_CHECKING, List, Type

from ...utilles import IOStatus
from .monomers import MiraiMonomer
from ..medium import Message
from .chain import MessageChain
from ...utilles.data_source_info import DataSourceInfo
from ...main.protocol import NetworkProtocol

if TYPE_CHECKING:
    from ...main.monomer import Monomer
    from .server_docker import MAHServerDocker


class MAHProtocol(NetworkProtocol):
    storage: Dict[Type["MAHServerDocker"], "MAHServerDocker"]

    async def medium_transport(self, action: str):
        server = list(self.storage.values())[-1]
        medium = await self.get_medium()
        if server.metadata.state in (IOStatus.CLOSED, IOStatus.CLOSE_WAIT):
            return
        if action.endswith("message"):
            rest = medium.get('rest')
            may_action = rest.get('type')
            target = medium.get("target")
            sender = self.scene.monomer_protocol.storage.get(target)
            if may_action:
                if may_action.startswith("Friend") and sender.compare("Friend"):
                    action = "sendFriendMessage"
                elif may_action.startswith("Group") and sender.compare("Member"):
                    if sender.parents:
                        target = sender.metadata.group_id
                        action = "sendGroupMessage"
            else:
                if sender.prime_tag == "Member":
                    if sender.parents:
                        target = sender.metadata.group_id
                        action = "sendGroupMessage"
                elif sender.prime_tag == "Friend":
                    action = "sendFriendMessage"
            resp = await server.behavior.session_handle(
                "POST",
                action,
                {
                    "sessionKey": server.metadata.session_key,
                    "target": target,
                    "messageChain": medium.get("content").dict()["__root__"],
                    **(
                        {"quote": rest.get("quote")} if medium.get("reply") else {}
                    )

                }
            )
            self.scene.edoves.logger.info(
                f"{self.scene.edoves.self.metadata.identifier}: "
                f"{action.replace('send','').replace('Message','')}({target})"
                f" <- {medium.get('content').to_text()}"
            )
            return resp

    async def parse_raw_data(self, data: Dict):
        ev_type: str = data.get("type")
        if not ev_type:
            return
        if ev_type.endswith("Message"):
            if not TYPE_CHECKING:
                sender_data: Dict = data.get("sender")
                sender_id = str(sender_data.get('id'))
                if ev_type.startswith("Friend"):
                    if not (sender := self.scene.monomers.get(sender_id)):
                        sender = MiraiMonomer(
                            self.scene.monomer_protocol,
                            sender_data.get("nickname"),
                            sender_id,
                            sender_data.get("remark")
                        )
                        sender.set_parent(self.scene.edoves.self)
                        self.scene.monomers.setdefault(sender.metadata.identifier, sender)
                    if sender.prime_tag == "Member":
                        sender.set_parent(self.scene.edoves.self)
                        sender.metadata.update_data("alias", sender_data.get("remark"))
                    sender.set_prime_tag("Friend")

                elif ev_type.startswith("Group") or ev_type.startswith("Temp"):
                    if not (sender := self.scene.monomers.get(sender_id)):
                        sender = MiraiMonomer(
                            self.scene.monomer_protocol,
                            sender_data.get("memberName"),
                            sender_id,
                            **{
                                "permission": sender_data.get("permission"),
                                "specialTitle": sender_data.get("specialTitle"),
                                "joinTimestamp": sender_data.get("joinTimestamp"),
                                "lastSpeakTimestamp": sender_data.get("lastSpeakTimestamp"),
                                "muteTimeRemaining": sender_data.get("muteTimeRemaining"),
                            }
                        )
                        self.scene.monomers[sender.metadata.identifier] = sender
                    elif sender.prime_tag == "Member":
                        sender.metadata.update_data("permission", sender_data.get("permission"))
                        sender.metadata.update_data("specialTitle", sender_data.get("specialTitle"))
                        sender.metadata.update_data("joinTimestamp", sender_data.get("joinTimestamp"))
                        sender.metadata.update_data("lastSpeakTimestamp", sender_data.get("lastSpeakTimestamp"))
                        sender.metadata.update_data("muteTimeRemaining", sender_data.get("muteTimeRemaining"))
                    elif sender.prime_tag == "Friend":
                        sender.metadata.update_data("alias", sender_data.get("memberName"))
                    sender.set_prime_tag("Member")

                    group_data: Dict = sender_data.get("group")
                    if not (group := self.scene.monomers.get(group_data.get('id'))):
                        group = MiraiMonomer(
                            self.scene.monomer_protocol,
                            group_data.get("name"),
                            group_data.get("id"),
                            **{
                                "permission": group_data.get("permission"),
                            }
                        )
                        self.scene.monomers.setdefault(group.metadata.identifier, group)
                    else:
                        group.metadata.update_data("name", group_data.get("name"))
                        group.metadata.update_data("permission", group_data.get("permission"))

                    group.set_child(self.scene.edoves.self)
                    group.set_prime_tag("Group")
                    if sender_id not in group.children:
                        group.set_child(sender)
                    sender.metadata.update_data("group_id", group.metadata.identifier)
                else:
                    if not (sender := self.scene.monomers.get(sender_id)):
                        sender = MiraiMonomer(
                            self.scene.monomer_protocol,
                            sender_data.get("nickname"),
                            sender_id,
                            sender_data.get("remark")
                        )
                        sender.set_parent(self.scene.edoves.self)
                        self.scene.monomers.setdefault(sender.metadata.identifier, sender)
                await self.post_message(
                    "AllMessage",
                    sender,
                    ev_type,
                    data.get("messageChain")
                )

    async def post_message(
            self,
            ev_type: str,
            purveyor: "Monomer",
            medium_type: str,
            content: List[Dict[str, str]]
    ):
        self.scene.module_protocol.set_medium(
            Message.create(purveyor, MessageChain, medium_type)(MessageChain.parse_obj(content))
        )
        await self.scene.module_protocol.broadcast_medium(ev_type)

    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="default"
    )
    medium_type = Dict
