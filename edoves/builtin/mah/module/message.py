from typing import Type
from edoves.main.module import MediumModule
from ..medium import Message
from edoves.builtin.mah import VERIFY_CODE
from edoves.main.typings import TMProtocol
from ..types import MType


async def test1(msg: Message):
    return msg.content


async def test2(msg: Message):
    return msg.type


class MessageModule(MediumModule):
    medium_type = Type[Message]
    identifier = VERIFY_CODE

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        self.new_handler(MType.ALL, test1, test2)

    def test3(self):
        self.protocol.modules.get("test")


@MessageModule.new_handler(MType.Friend)
def test(msg: Message):
    return msg.purveyor
