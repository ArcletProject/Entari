from typing import Optional, Union, Any
from arclet.edoves.main.interact.monomer import BaseMonoBehavior, Monomer
from arclet.edoves.main.protocol import AbstractProtocol

from .medium import Message, Request, DictMedium


class MiddlewareBehavior(BaseMonoBehavior):
    protocol: AbstractProtocol

    def activate(self):
        self.protocol = self.io.protocol

    async def revoke(self, medium: Message, target_message_id: int = None):
        await self.protocol.screen.push(
            DictMedium().create(
                self.io,
                {
                    "target": target_message_id if target_message_id else medium.id
                },
                "MessageRevoke"
            )
        )
        await self.protocol.execution_handle()

    async def nudge(self, target: Union[str, Monomer, None], **rest):
        resp = await self.protocol.screen.push(
            DictMedium().create(
                self.io,
                {
                    "target": target if isinstance(target, str) else target.metadata.identifier,
                    "rest": rest
                },
                "NudgeSend"
            )
        )
        await self.protocol.execution_handle()
        resp_data: DictMedium = await resp.wait_response()
        self.protocol.screen.edoves.logger.info(
            f"{self.protocol.current_scene.protagonist.metadata.identifier}: "
            f"{resp_data.type}({resp_data.content['id']}) <- Nudge"
        )

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
            await self.nudge(target.metadata.identifier, **rest)

        resp = await self.protocol.screen.push(
            DictMedium().create(
                self.io,
                {
                    "target": target.metadata.identifier,
                    "reply": reply,
                    "content": medium.content.to_sendable(),
                    "rest": rest
                },
                "MessageSend"
            )
        )
        await self.protocol.execution_handle()
        resp_data: DictMedium = await resp.wait_response()
        self.protocol.screen.edoves.logger.info(
            f"{self.protocol.current_scene.protagonist.metadata.identifier}: "
            f"{resp_data.type}({resp_data.content.get('id') or target.metadata.identifier})"
            f" <- {medium.content.to_text()}"
        )
        return resp_data.content.get('messageId')

    async def request_accept(self, medium: Request, msg: str = None):
        await self.protocol.screen.push(
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
        await self.protocol.execution_handle()

    async def request_reject(self, medium: Request, msg: str = None):
        await self.protocol.screen.push(
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
        await self.protocol.execution_handle()

    async def relationship_remove(self, target: Union[str, Monomer],  relationship: str = None):
        target = await self.relationship_get(target, relationship) if isinstance(target, str) else target
        await self.protocol.screen.push(
            DictMedium().create(
                self.io,
                {
                    "relationship": target.prime_tag,
                    "target": target,
                },
                "RelationshipRemove"
            )
        )
        await self.protocol.execution_handle()

    async def relationship_get(self, target: str, relationship: str, **rest):
        resp = await self.protocol.screen.push(
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
        await self.protocol.execution_handle()
        return await resp.wait_response()

    async def change_monomer_status(self, target: Monomer, status: str, **rest):
        await self.protocol.screen.push(
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
        await self.protocol.execution_handle()

    async def change_metadata(
            self,
            meta: str,
            value: Any,
            target: Optional["Monomer"] = None,
            **addition
    ):
        await self.protocol.screen.push(
            DictMedium().create(
                self.io,
                {
                    "target": target or self.io,
                    "meta": meta,
                    "rest": addition,
                },
                "ChangeMonomerMetadata"
            )
        )
        await self.protocol.execution_handle()
