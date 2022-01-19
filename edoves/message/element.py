import json
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING
from base64 import b64decode, b64encode
from pydantic import validator
import aiohttp
from abc import ABC
from ..utilles import DataStructure

if TYPE_CHECKING:
    from .chain import MessageChain


class MessageElement(ABC, DataStructure):
    type: str

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))

    def to_serialization(self) -> str:
        return f"[{self.type}:{json.dumps(self.dict(exclude={'type'}))}]".replace('\n', '\\n').replace('\t', '\\t')

    def to_text(self) -> str:
        return ""


class MediaElement(MessageElement):
    url: Optional[str] = None
    base64: Optional[str] = None

    async def get_bytes(self) -> bytes:
        if self.url and not self.base64:
            async with aiohttp.request("GET", self.url) as response:
                if response.status != 200:
                    raise ConnectionError(response.status, await response.text())
                data = await response.content.readexactly(response.content_length)
                self.base64 = str(b64encode(data), encoding='utf-8')
                return data
        if self.base64:
            return b64decode(self.base64)

    def to_sendable(self, path: Optional[Union[Path, str]] = None, data_bytes: Optional[bytes] = None):
        if sum([bool(self.url), bool(path), bool(self.base64)]) > 1:
            raise ValueError("Too many binary initializers!")
        if path:
            if isinstance(path, str):
                path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"{path} is not exist!")
            self.base64 = str(b64encode(path.read_bytes()), encoding='utf-8')
        elif data_bytes:
            self.base64 = str(b64encode(data_bytes), encoding='utf-8')


class Quote(MessageElement):
    """表示消息中回复其他消息/用户的部分, 通常包含一个完整的消息链(`origin` 属性)"""
    type: str = "Quote"
    id: int
    groupId: int
    senderId: int
    targetId: int
    origin: "MessageChain"

    @validator("origin", pre=True, allow_reuse=True)
    def _(cls, v):
        from .chain import MessageChain
        return MessageChain(v)

    def to_serialization(self) -> str:
        return f"[mirai:Quote:{{\"id\":{self.id},\"origin\":{self.origin}}}]"


class Text(MessageElement):
    type: str = "Text"
    text: str

    def __init__(self, text: str, **kwargs) -> None:
        """实例化一个 Plain 消息元素, 用于承载消息中的文字.

        Args:
            text (str): 元素所包含的文字
        """
        super().__init__(text=text, **kwargs)

    def to_text(self):
        return self.text.replace('\n', '\\n').replace('\t', '\\t')

    def to_serialization(self) -> str:
        return self.text.replace('\n', '\\n').replace('\t', '\\t')


class At(MessageElement):
    """该消息元素用于承载消息中用于提醒/呼唤特定用户的部分."""

    type: str = "At"
    target: int
    display: Optional[str] = None

    def __init__(self, target: int, **kwargs) -> None:
        """实例化一个 At 消息元素, 用于承载消息中用于提醒/呼唤特定用户的部分.

        Args:
            target (int): 需要提醒/呼唤的特定用户的 QQ 号(或者说 id.)
        """
        super().__init__(target=target, **kwargs)

    def to_text(self) -> str:
        return f"@{str(self.display)}" if self.display else f"@{self.target}"


class AtAll(MessageElement):
    """该消息元素用于群组中的管理员提醒群组中的所有成员"""
    type: str = "AtAll"

    def to_text(self) -> str:
        return "@全体成员"


class Voice(MediaElement):
    type = "Voice"
    voiceId: Optional[str]
    length: Optional[int]

    def __init__(
            self,
            voiceId: Optional[str] = None,
            url: Optional[str] = None,
            path: Optional[Union[Path, str]] = None,
            base64: Optional[str] = None,
            data_bytes: Optional[bytes] = None,
            **kwargs
    ):
        super().__init__(
            voiceId=voiceId,
            url=url,
            base64=base64,
            **kwargs
        )
        self.to_sendable(path, data_bytes)

    def to_text(self) -> str:
        return "[语音]"


class Image(MediaElement):
    """该消息元素用于承载消息中所附带的图片."""
    type = "Image"
    imageId: Optional[str] = None
    url: Optional[str] = None
    base64: Optional[str] = None

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
        return "[图片]"

