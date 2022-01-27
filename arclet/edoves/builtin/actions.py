import inspect
from typing import Optional
from ..main.action import ExecutiveAction
from .medium import Message


class MessageAction(ExecutiveAction):
    data: Message

    def __init__(self, action: str, message: Message):
        super().__init__(message, action)

    async def execute(self):
        return await self.target.action(self.action)(
            self.data
        )


class MessageRevoke(MessageAction):
    message_id: int

    def __init__(self, message: Message, target: int = None):
        self.message_id = target
        super().__init__("revoke", message)

    async def execute(self):
        return await self.target.action(self.action)(
            self.data, target=self.message_id
        )


class MessageSend(MessageAction):

    def __init__(self, message: Optional[Message] = None):
        if not message:
            try:
                lcs = inspect.currentframe().f_back.f_back.f_locals
                for v in lcs.values():
                    if isinstance(v, Message):
                        message = v
            except AttributeError:
                raise ValueError
            else:
                if not message:
                    raise ValueError
        super().__init__("send_with", message)


class MessageSendDirectly(MessageSend):
    async def execute(self):
        return await self.target.action(self.action)(
            self.data, type=self.data.type
        )
