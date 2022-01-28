from ..main.monomer import BaseMonoBehavior
from ..main.protocol import NetworkProtocol, MonomerProtocol
from .medium import Message


class MessageBehavior(BaseMonoBehavior):
    n_protocol: NetworkProtocol
    m_protocol: MonomerProtocol

    def activate(self):
        self.n_protocol = self.io.metadata.protocol.scene.network_protocol
        self.m_protocol = self.io.metadata.protocol

    async def revoke(self, medium: Message, target: int = None):
        await self.m_protocol.set_medium(
            {
                "target": target if target else medium.content.find("Source").id
            }
        )
        await self.n_protocol.medium_transport("message_revoke")

    async def nudge(self, target: str, **rest):
        await self.m_protocol.set_medium(
            {
                "target": target,
                "rest": rest
            }
        )
        await self.n_protocol.medium_transport("nudge_send")

    async def send_with(self, medium: Message, reply: bool = False, nudge: bool = False, **rest):
        if nudge:
            await self.m_protocol.set_medium(
                {
                    "target": medium.purveyor.metadata.identifier,
                    "rest": rest
                }
            )
            await self.n_protocol.medium_transport("nudge_send")

        await self.m_protocol.set_medium(
            {
                "target": medium.purveyor.metadata.identifier,
                "reply": reply,
                "content": medium.content.replace_type("Text", "Plain").to_sendable(),
                "rest": rest
            }
        )
        resp_data = await self.n_protocol.medium_transport("message_send")
        return resp_data.get('messageId')


class MonoMetaBehavior(BaseMonoBehavior):
    n_protocol: NetworkProtocol
    m_protocol: MonomerProtocol

    def activate(self):
        self.n_protocol = self.io.metadata.protocol.scene.network_protocol
        self.m_protocol = self.io.metadata.protocol
