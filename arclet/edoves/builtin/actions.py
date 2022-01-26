import inspect
from typing import Optional
from ..main.action import ExecutiveAction
from .medium import Message


class MessageAction(ExecutiveAction):
    data: Message
    action: str

    def __init__(self, action: str, message: Message):
        super().__init__(message)
        self.action = action

    async def execute(self):
        return await self.target.action(self.action)(
            self.data
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
