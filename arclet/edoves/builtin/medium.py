from typing import Dict, Union, Iterable, Optional
import json as JSON

from arclet.edoves.main.typings import TData
from arclet.edoves.main.medium import BaseMedium, Monomer
from .message.chain import MessageChain, MessageElement


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

    def __init__(self, *elements: Union[Iterable[MessageElement], MessageElement, str], target: Monomer = None):
        super().__init__()
        self.id = ""
        self.content = MessageChain.create(*elements)
        self.purveyor = target
        self.type = "Message"

    def set(self, *elements: Union[Iterable[MessageElement], MessageElement, str]):
        """
        设置消息内容。

        Returns:
            Message: 返回一个新的消息媒介。
        """
        new = Message().create(self.purveyor, MessageChain.create(*elements), self.type)
        new.id = self.id
        new.time = self.time
        return new

    def __call__(self, *args, **kwargs):
        return self.set(*args)

    async def send(
            self,
            target: Optional[Union[int, str, Monomer]] = None,
            reply: bool = False,
    ):
        if target:
            return await self.action("send_with")(self, target, reply)
        return await self.action("send_with")(self, reply=reply)

    def __await__(self):
        return self.send().__await__()


class Notice(BaseMedium):
    operator: Optional[Monomer]
    content: Dict[str, TData]  # 子类请使用TypedDict或Literal代替str来固定meta

    __export__ = ["operator"]

    def get_data(self, key: str):
        return self.content.get(key)


class Request(BaseMedium):
    event: str
    content: Dict[str, TData]

    def get_data(self, key: str):
        return self.content.get(key)
