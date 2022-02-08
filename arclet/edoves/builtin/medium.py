from typing import Dict, Union, Iterable, Optional
import json as JSON

from ..main.typings import TData
from ..main.medium import BaseMedium, Monomer
from ..main.message.chain import MessageChain, MessageElement


class DictMedium(BaseMedium):
    """基础的Medium，用于存储字典数据。"""
    content: Dict[str, TData]

    def json_loads(self, json: Union[dict, str]):
        if isinstance(json, str):
            json = JSON.loads(json)
        self.content = json
        return self


class Message(BaseMedium):
    id: str
    content: MessageChain

    __metadata__ = [*BaseMedium.__metadata__, "id"]

    def __init__(self, *elements: Union[Iterable[MessageElement], MessageElement, str], target: Monomer = None):
        super().__init__()
        self.id = ""
        self.content = MessageChain.create(*elements)
        self.purveyor = target
        self.type = "Message"

    def set(self, *elements: Union[Iterable[MessageElement], MessageElement, str]):
        self.content = MessageChain.create(*elements)
        return self

    async def send(self, target: Optional[Union[int, str, Monomer]] = None):
        if target:
            return await self.action("send_with")(self, target)
        return await self.action("send_with")(self)


class Notice(BaseMedium):
    operator: Optional[Monomer]
    content: Dict[str, TData]  # 子类请使用TypedDict或Literal代替str来固定meta

    __metadata__ = [*BaseMedium.__metadata__, "operator"]

    def get_data(self, key: str):
        return self.content.get(key)


class Request(BaseMedium):
    event: str
    content: Dict[str, TData]

    __metadata__ = [*BaseMedium.__metadata__, "event"]

    def get_data(self, key: str):
        return self.content.get(key)
