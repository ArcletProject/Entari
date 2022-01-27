from typing import Dict, Union, Iterable, Optional
import json as JSON

from ..main.typings import TData
from ..main.medium import BaseMedium, Monomer
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

    def __init__(
            self,
            *elements: Union[Iterable[MessageElement], MessageElement, str],
            target: Monomer = None
    ):
        self.content = MessageChain.create(*elements)
        self.purveyor = target
        self.type = "Message"

    def set(self, *elements: Union[Iterable[MessageElement], MessageElement, str]):
        self.content = MessageChain.create(*elements)
        return self

    async def send(self):
        return await self.action("send_with")(self)


class Notice(BaseMedium):
    operator: Optional[Monomer]
    content: Dict[str, TData]

    __metadata__ = [*BaseMedium.__metadata__, "operator"]

    def __getattr__(self, item):
        return self.content.get(item)

    def __setattr__(self, key, value):
        if key in self.__metadata__:
            super().__setattr__(self, key, value)
        self.content[key] = value

