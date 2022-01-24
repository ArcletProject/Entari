from typing import Dict, TYPE_CHECKING, List

from .monomers import Friend, Member, Group
from ..medium import Message
from .chain import MessageChain
from ...main.medium import BaseMedium
from ...utilles.data_source_info import DataSourceInfo
from ...main.protocol import NetworkProtocol

if TYPE_CHECKING:
    from ...main.monomer import Monomer


class MAHProtocol(NetworkProtocol):

    async def medium_transport(self, data: BaseMedium):
        return await self.current.session_handle(data.content)

    async def parse_raw_data(self, data: Dict):
        ev_type = data.get("type")
        if not ev_type:
            return
        if ev_type.endswith("Message"):
            if not TYPE_CHECKING:
                if ev_type.startswith("Friend"):
                    sender_data: Dict = data.get("sender")
                    if not (sender := self.scene.monomers.get(sender_data.get('id'))):
                        sender = Friend(
                            self.scene.monomer_protocol,
                            sender_data.get("nickname"),
                            sender_data.get("id"),
                            sender_data.get("remark")
                        )
                        sender.add_tags("Friend")
                        sender.set_parent(self.scene.edoves.self)
                        self.scene.monomers.setdefault(sender.metadata.identifier, sender)
                elif ev_type.startswith("Group") or ev_type.startswith("Temp"):
                    sender_data: Dict = data.get("sender")
                    if not (sender := self.scene.monomers.get(sender_data.get('id'))):
                        sender = Member.parse_obj(
                            self.scene.monomer_protocol,
                            sender_data
                        )
                        sender.add_tags("Member")
                        self.scene.monomers.setdefault(sender.metadata.identifier, sender)
                    group_data: Dict = sender_data.get("group")
                    if not (group := self.scene.monomers.get(group_data.get('id'))):
                        group = Group(
                            self.scene.monomer_protocol,
                            group_data.get("name"),
                            group_data.get("permission"),
                            group_data.get("id")
                        )
                        group.add_tags("Group")
                        self.scene.monomers.setdefault(group.metadata.identifier, group)
                    group.set_child(self.scene.edoves.self)
                    if sender not in group.children:
                        group.set_child(sender)
                else:
                    sender_data: Dict = data.get("sender")
                    if not (sender := self.scene.monomers.get(sender_data.get('id'))):
                        sender = Friend(
                            self.scene.monomer_protocol,
                            sender_data.get("nickname"),
                            sender_data.get("id"),
                            sender_data.get("remark")
                        )
                        sender.add_tags("Stranger")
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
