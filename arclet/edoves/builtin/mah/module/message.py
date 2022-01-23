from typing import Type
from ....main.module import BaseModule
from ...medium import Message
from ....builtin.mah import VERIFY_CODE


class MessageModule(BaseModule):
    medium_type = Type[Message]
    identifier = VERIFY_CODE
