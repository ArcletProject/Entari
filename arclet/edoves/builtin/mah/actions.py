from ..actions import MessageSend
from .chain import Source

MessageSend = MessageSend


class Reply(MessageSend):
    async def execute(self):
        return await self.target.action(self.action)(
            self.data, reply=True, quote=self.data.content.find(Source).id
        )
