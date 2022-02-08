import inspect
from typing import Optional, Union, Any, TYPE_CHECKING
from .medium import Message, Request
from ..main.action import ExecutiveAction


if TYPE_CHECKING:
    from ..main.monomer import Monomer


class GetMonomer(ExecutiveAction):
    mono_id: str
    rs: str

    def __init__(self, target: Union[int, str], relationship: str, **kwargs):
        self.mono_id = str(target)
        self.rs = relationship
        self.rest = kwargs
        super().__init__("relationship_get")

    async def execute(self):
        entity = self.target.metadata.protocol.storage.get(self.mono_id)
        if not entity:
            return await self.target.action(self.action)(
                self.mono_id, self.rs, **self.rest
            )
        return entity


class ChangeStatus(ExecutiveAction):
    status: str
    value: Any

    def __init__(self, target: "Monomer", status: str, value: Any, **kwargs):
        super(ChangeStatus, self).__init__("change_monomer_status")
        self.target = target
        self.status = status
        self.value = value
        self.rest = kwargs

    async def execute(self):
        return await self.target.action(self.action)(
            self.target, self.status, **{self.status: self.value, **self.rest}
        )


class MessageAction(ExecutiveAction):
    data: Message

    def __init__(self, action: str, message: Message):
        super().__init__(action)
        self.target = message.purveyor
        self.data = message

    async def execute(self):
        return await self.target.action(self.action)(
            self.data
        )


class MessageRevoke(MessageAction):
    message_id: int

    def __init__(self, message: Message, target: int = None):
        super().__init__("revoke", message)
        self.message_id = target

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


class RequestAction(ExecutiveAction):
    data: Request
    msg: str

    def __init__(self, action: str, request: Request, msg: str):
        super().__init__(action)
        self.msg = msg
        self.data = request

    async def execute(self):
        return await self.target.action(self.action)(
            self.data, msg=self.msg
        )


class RequestAccept(RequestAction):
    def __init__(self, request: Optional[Request] = None, msg: Optional[str] = ""):
        if not request:
            try:
                lcs = inspect.currentframe().f_back.f_back.f_locals
                for v in lcs.values():
                    if isinstance(v, Request):
                        request = v
            except AttributeError:
                raise ValueError
            else:
                if not Request:
                    raise ValueError
        super().__init__("accept", request, msg)


class RequestReject(RequestAction):
    def __init__(self, request: Optional[Request] = None, msg: Optional[str] = ""):
        if not request:
            try:
                lcs = inspect.currentframe().f_back.f_back.f_locals
                for v in lcs.values():
                    if isinstance(v, Request):
                        request = v
            except AttributeError:
                raise ValueError
            else:
                if not Request:
                    raise ValueError
        super().__init__("accept", request, msg)
