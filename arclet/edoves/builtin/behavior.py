from ..main.monomer import BaseMonoBehavior
from ..main.protocol import NetworkProtocol
from .medium import Message


class MessageBehavior(BaseMonoBehavior):
    protocol: NetworkProtocol

    def activate(self):
        self.protocol = self.io.metadata.protocol.scene.network_protocol

    async def revoke(self, medium: Message, target: int = None):
        self.protocol.set_medium(
            {
                "target": target if target else medium.content.find("Source").id
            }
        )
        await self.protocol.medium_transport("message_revoke")

    async def nudge(self, target: str, **rest):
        self.protocol.set_medium(
            {
                "target": target,
                "rest": rest
            }
        )
        await self.protocol.medium_transport("nudge_send")

    async def send_with(self, medium: Message, reply: bool = False, nudge: bool = False, **rest):
        if nudge:
            self.protocol.set_medium(
                {
                    "target": medium.purveyor.metadata.identifier,
                    "rest": rest
                }
            )
            await self.protocol.medium_transport("nudge_send")

        self.protocol.set_medium(
            {
                "target": medium.purveyor.metadata.identifier,
                "reply": reply,
                "content": medium.content.replace_type("Text", "Plain").to_sendable(),
                "rest": rest
            }
        )
        resp_data = await self.protocol.medium_transport("message_send")
        return resp_data.get('messageId')


class MonoMetaBehavior(BaseMonoBehavior):
    protocol: NetworkProtocol

    def activate(self):
        self.protocol = self.io.metadata.protocol.scene.network_protocol
