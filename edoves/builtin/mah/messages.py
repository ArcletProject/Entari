import json as JSON
from xml import sax
from enum import Enum
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Union, List
from ...message.element import MessageElement, DataStructure, Quote, Text, Image
from pydantic import Field

if TYPE_CHECKING:
    from ...message.chain import MessageChain

Plain = Text


class Source(MessageElement):
    """表示消息在一个特定聊天区域内的唯一标识"""
    type: str = "Source"
    id: int
    time: int


class Face(MessageElement):
    """表示消息中所附带的表情, 这些表情大多都是聊天工具内置的."""
    type: str = "Face"
    faceId: int
    name: Optional[str] = None

    def to_text(self) -> str:
        return f"[表情:{self.name}]" if self.name else f"[表情:{self.faceId}]"


class Xml(MessageElement):
    type = "Xml"
    xml: str

    def __init__(self, xml, *_, **__) -> None:
        super().__init__(xml=xml)

    def to_text(self) -> str:
        return "[XML消息]"

    def get_xml(self):
        return sax.parseString(self.xml, sax.handler.ContentHandler())


class Json(MessageElement):
    type = "Json"
    Json: str = Field(..., alias="json")

    def __init__(self, json: Union[dict, str], **kwargs) -> None:
        if isinstance(json, dict):
            json = JSON.dumps(json)
        super().__init__(json=json, **kwargs)

    def to_text(self) -> str:
        return "[JSON消息]"

    def get_json(self) -> dict:
        return JSON.loads(self.Json)


class App(MessageElement):
    type = "App"
    content: str

    def to_text(self) -> str:
        return f"[APP消息:{JSON.loads(self.content)['prompt']}]"

    def get_meta_content(self) -> dict:
        return JSON.loads(self.content)['meta']


class PokeMethods(Enum):
    ChuoYiChuo = "ChuoYiChuo"
    BiXin = "BiXin"
    DianZan = "DianZan"
    XinSui = "XinSui"
    LiuLiuLiu = "LiuLiuLiu"
    FangDaZhao = "FangDaZhao"
    BaoBeiQiu = "BaoBeiQiu"
    Rose = "Rose"
    ZhaoHuanShu = "ZhaoHuanShu"
    RangNiPi = "RangNiPi"
    JeiYin = "JeiYin"
    ShouLei = "ShouLei"
    GouYin = "GouYin"
    ZhuaYiXia = "ZhuaYiXia"
    SuiPing = "SuiPing"
    QiaoMen = "QiaoMen"


class Poke(MessageElement):
    type = "Poke"
    name: PokeMethods

    def to_text(self) -> str:
        return f"[戳一戳:{self.name}]"


class Dice(MessageElement):
    type = "Dice"
    value: int

    def to_text(self) -> str:
        return f"[骰子:{self.value}]"


class File(MessageElement):
    type = "File"
    file_id: str
    name: str
    size: int

    def to_text(self) -> str:
        return f'[文件:{self.name}]'


class ImageType(Enum):
    Friend = "Friend"
    Group = "Group"
    Temp = "Temp"
    Unknown = "Unknown"


class FlashImage(Image):
    """该消息元素用于承载消息中所附带的图片."""
    type = "FlashImage"

    def __init__(
            self,
            imageId: Optional[str] = None,
            url: Optional[str] = None,
            path: Optional[Union[Path, str]] = None,
            base64: Optional[str] = None,
            data_bytes: Optional[bytes] = None,
            **kwargs
    ):
        super().__init__(
            imageId=imageId,
            url=url,
            base64=base64,
            **kwargs
        )
        self.to_sendable(path, data_bytes)

    def to_text(self) -> str:
        return "[闪照]"


class MusicShare(MessageElement):
    type = "MusicShare"
    kind: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    jumpUrl: Optional[str]
    pictureUrl: Optional[str]
    musicUrl: Optional[str]
    brief: Optional[str]

    def to_text(self) -> str:
        return f"[音乐分享:{self.title}]"


class ForwardNode(DataStructure):
    """表示合并转发中的一个节点"""
    senderId: int
    time: int
    senderName: str
    messageChain: Optional["MessageChain"]
    messageId: Optional[int]


class Forward(MessageElement):
    """
    指示合并转发信息

    nodeList (List[ForwardNode]): 转发的消息节点
    """

    type = "Forward"
    nodeList: List[ForwardNode]

    def to_text(self) -> str:
        return f"[合并转发:共{len(self.nodeList)}条]"


def _update_forward_refs():
    from ...message.chain import MessageChain

    Quote.update_forward_refs(MessageChain=MessageChain)
    ForwardNode.update_forward_refs(MessageChain=MessageChain)


if TYPE_CHECKING:
    _update_forward_refs()
