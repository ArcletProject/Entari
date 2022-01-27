from ..actions import MessageSend
from .chain import Source


class Reply(MessageSend):
    async def execute(self):
        return await self.target.action(self.action)(
            self.data, reply=True, quote=self.data.content.find(Source).id
        )


class NudgeWith(MessageSend):
    async def execute(self):
        return await self.target.action(self.action)(
            self.data, nudge=True
        )


class Nudge(MessageSend):
    async def execute(self):
        return await self.target.action('nudge')(
            self.target.metadata.identifier
        )


send_message = MessageSend
send_nudge = Nudge
nudge_with = NudgeWith
reply = Reply
