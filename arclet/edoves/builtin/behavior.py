from ..main.monomer import BaseMonoBehavior
from ..main.protocol import NetworkProtocol
from .medium import Message


class MessageBehavior(BaseMonoBehavior):
    protocol: NetworkProtocol

    def activate(self):
        self.protocol = self.io.metadata.protocol.scene.network_protocol

    async def send_with(self, medium: Message, reply: bool = False, nudge: bool = False, **rest):
        self.protocol.set_medium(
            {
                "target": medium.purveyor.metadata.identifier,
                "reply": reply,
                "nudge": nudge,
                "content": medium.content.replace_type("Text", "Plain").to_sendable(),
                "rest": rest
            }
        )
        resp_data = await self.protocol.medium_transport("send_message")
