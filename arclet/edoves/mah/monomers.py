from enum import Enum
from typing import Optional, TYPE_CHECKING

from arclet.edoves.main.monomer import Monomer, MonoMetaComponent
from arclet.edoves.builtin.behavior import MiddlewareBehavior
from arclet.edoves.builtin.medium import Message

if TYPE_CHECKING:
    from .protocol import MAHProtocol


class Permission(str, Enum):
    """描述群成员在群组中的权限"""

    UNKNOWN = "NONE"  # 未知或未给
    Member = "MEMBER"  # 普通成员
    Administrator = "ADMINISTRATOR"  # 管理员
    Owner = "OWNER"  # 群主


class Equipment(str, Enum):
    """客户端的设备名称信息"""

    Mobile = "MOBILE"  # 移动端E
    Windows = "WINDOWS"  # win电脑
    MacOS = "MACOS"  # mac电脑


class MEMetadata(MonoMetaComponent):
    protocol: "MAHProtocol"
    permission: Permission
    group_id: Optional[str]

    specialTitle: Optional[str]
    joinTimestamp: Optional[int]
    lastSpeakTimestamp: Optional[int]
    mutetimeRemaining: Optional[int]

    __limit__ = ["group_id", "permission"]


class MahEntity(Monomer):
    prefab_metadata = MEMetadata
    prefab_behavior = MiddlewareBehavior

    def __init__(
            self,
            protocol: "MAHProtocol",
            nickname: str,
            identifier: Optional[str] = None,
            remark: Optional[str] = None,
    ):
        super().__init__(protocol, nickname, identifier, remark)

    @property
    def current_group(self):
        return self.get_parent(self.metadata.group_id) if hasattr(self.metadata, "group_id") else None

    def avatar(self):
        return f'https://q4.qlogo.cn/g?b=qq&nk={self.metadata.pure_id}&s=140'

    async def reply(self, *args):
        msg = Message(*args, target=self)
        msg.type = self.prime_tag + "Message"
        return await self.get_component(MiddlewareBehavior).send_with(
            msg, reply=True,
        )
