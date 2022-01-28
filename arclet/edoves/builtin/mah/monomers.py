from enum import Enum
from typing import Optional, Dict, Any

from ...main.monomer import Monomer, MonoMetaComponent
from ..behavior import MessageBehavior
from .chain import MessageChain
from ...main.typings import TMonoProtocol


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


class MiraiMonoMetadata(MonoMetaComponent):
    specialTitle: Optional[str]
    permission: Permission
    joinTimestamp: Optional[int]
    lastSpeakTimestamp: Optional[int]
    mutetimeRemaining: Optional[int]
    group_id: Optional[str]


class MiraiMonomer(Monomer):
    prefab_metadata = MiraiMonoMetadata
    prefab_behavior = MessageBehavior

    def __init__(
            self,
            protocol: TMonoProtocol,
            nickname: str,
            identifier: Optional[str] = None,
            remark: Optional[str] = None,
            **data: Dict[str, Any]
    ):
        super().__init__(protocol, nickname, identifier, remark)
        for k, v in data.items():
            self.get_component(MiraiMonoMetadata).update_data(k, v)

    @property
    def current_group(self):
        return self.parents[self.metadata.group_id] if hasattr(self.metadata, "group_id") else None

    def avatar(self):
        return f'https://q4.qlogo.cn/g?b=qq&nk={self.metadata.identifier}&s=140'

    async def reply(self, *args):
        await self.metadata.protocol.set_medium(
            {
                "target": self.metadata.identifier,
                "reply": True,
                "content": MessageChain.create(*args).replace_type("Text", "Plain")
            }
        )
        resp_data = await self.metadata.protocol.scene.network_protocol.medium_transport("message_send")
        return resp_data['messageId']
