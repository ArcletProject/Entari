from typing import Optional, Union
from ..main.monomer import BaseMonoBehavior, Monomer
from ..main.protocol import AbstractProtocol
from .medium import Message, Request, DictMedium


class MiddlewareBehavior(BaseMonoBehavior):
    protocol: AbstractProtocol

    def activate(self):
        self.protocol = self.io.metadata.protocol

    async def revoke(self, medium: Message, target_message_id: int = None):
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "target": target_message_id if target_message_id else medium.id
                },
                "MessageRevoke"
            )
        )
        await self.protocol.data_parser_dispatch("post")

    async def nudge(self, target: Union[str, Monomer], **rest):
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "target": target if isinstance(target, str) else target.metadata.pure_id,
                    "rest": rest
                },
                "NudgeSend"
            )
        )
        await self.protocol.data_parser_dispatch("post")

    async def send_with(
            self,
            medium: Message,
            target: Optional[Monomer] = None,
            reply: bool = False,
            nudge: bool = False,
            **rest
    ):
        target = target or medium.purveyor
        if nudge:
            await self.nudge(target.metadata.pure_id, **rest)

        resp = await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "target": target.metadata.pure_id,
                    "reply": reply,
                    "content": medium.content.to_sendable(),
                    "rest": rest
                },
                "MessageSend"
            )
        )
        await self.protocol.data_parser_dispatch("post")
        resp_data: DictMedium = await resp.wait_response()
        self.protocol.scene.edoves.logger.info(
            f"{self.protocol.scene.protagonist.metadata.pure_id}: "
            f"{resp_data.type}({resp_data.content['id']})"
            f" <- {medium.content.to_text()}"
        )
        return resp_data.content.get('messageId')

    async def request_accept(self, medium: Request, msg: str = None):
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "event": medium.type,
                    "operate": 0,
                    "eventId": medium.event,
                    "msg": msg,
                    "content": medium.content
                },
                "Accept"
            )
        )
        await self.protocol.data_parser_dispatch("post")

    async def request_reject(self, medium: Request, msg: str = None):
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "event": medium.type,
                    "operate": 1,
                    "eventId": medium.event,
                    "msg": msg,
                    "content": medium.content
                },
                "Reject"
            )
        )
        await self.protocol.data_parser_dispatch("post")

    async def relationship_remove(self, target: Union[str, Monomer],  relationship: str = None):
        target = await self.relationship_get(target, relationship) if isinstance(target, str) else target
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "relationship": target.prime_tag,
                    "target": target,
                },
                "RelationshipRemove"
            )
        )
        await self.protocol.data_parser_dispatch("post")

    async def relationship_get(self, target: str, relationship: str, **rest):
        resp = await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "relationship": relationship,
                    "target": target,
                    "rest": rest
                },
                "RelationshipGet"
            )
        )
        await self.protocol.data_parser_dispatch("post")
        return await resp.wait_response()

    async def change_monomer_status(self, target: Monomer, status: str, **rest):
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "target": target,
                    "status": status,
                    "rest": rest,
                },
                "ChangeMonomerStatus"
            )
        )
        await self.protocol.data_parser_dispatch("post")

    async def change_monomer_metadata(self, target: Monomer, meta: str, **rest):
        await self.protocol.push_medium(
            DictMedium().create(
                self.io,
                {
                    "target": target,
                    "meta": meta,
                    "rest": rest,
                },
                "ChangeMonomerMetadata"
            )
        )
        await self.protocol.data_parser_dispatch("post")
