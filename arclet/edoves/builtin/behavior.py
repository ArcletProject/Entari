from ..main.monomer import BaseMonoBehavior
from ..main.protocol import NetworkProtocol
from .medium import Message


class MessageBehavior(BaseMonoBehavior):
    protocol: NetworkProtocol

    def activate(self):
        self.protocol = self.get_component("metadata").protocol

    async def send_with(self, medium: Message, reply: bool = False, nudge: bool = False):
        sendable_data = await self.protocol.transform_medium(medium)
        self.protocol.set_medium(
            {
                "target": self.io.metadata.identifier,
                "reply": reply,
                "nudge": nudge,
                "content": sendable_data
            }
        )
