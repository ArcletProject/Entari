from typing import Dict, Union, Iterable
import json as JSON

from ..main.typings import TData
from ..main.medium import BaseMedium
from ..message.chain import MessageChain, MessageElement


class JsonMedium(BaseMedium):
    content: Dict[str, TData]

    def json_loads(self, json: Union[dict, str]):
        if isinstance(json, str):
            json = JSON.loads(json)
        self.content = json
        return self


class Message(BaseMedium):
    content: MessageChain

    def set(self, *elements: Union[Iterable[MessageElement], MessageElement, str]):
        self.content = MessageChain.create(*elements)
        return self

    async def send(self):
        return await self.action("send_with")(self)
