from enum import Enum
from typing import Optional, Dict

from ...main.monomer import Monomer, MonoMetaComponent
from ..behavior import MessageBehavior
from ...main.typings import TMonoProtocol


class Permission(str, Enum):
    """描述群成员在群组中的权限"""

    Member = "MEMBER"  # 普通成员
    Administrator = "ADMINISTRATOR"  # 管理员
    Owner = "OWNER"  # 群主


class Equipment(str, Enum):
    """客户端的设备名称信息"""

    Mobile = "MOBILE"  # 移动端E
    Windows = "WINDOWS"  # win电脑
    MacOS = "MACOS"  # mac电脑


class GroupData(MonoMetaComponent):
    permission: Permission


class MemberData(GroupData):
    joinTimestamp: Optional[int]
    lastSpeakTimestamp: Optional[int]
    mutetimeRemaining: Optional[int]


class Friend(Monomer):
    prefab_behavior = MessageBehavior


class Stranger(Monomer):
    prefab_behavior = MessageBehavior


class Member(Monomer):
    prefab_metadata = MemberData
    prefab_behavior = MessageBehavior

    def __init__(
            self,
            protocol: TMonoProtocol,
            name: str,
            permission: str,
            identifier: Optional[int] = None,
            alias: Optional[str] = None,
            join_timestamp: Optional[int] = None,
            last_speak_timestamp: Optional[int] = None,
            mutetime_remaining: Optional[int] = None
    ):
        super().__init__(protocol, name, identifier, alias)
        self.metadata.permission = Permission(permission)
        self.metadata.joinTimestamp = join_timestamp
        self.metadata.lastSpeakTimestamp = last_speak_timestamp
        self.metadata.mutetimeRemaining = mutetime_remaining

    @classmethod
    def parse_obj(cls, protocol: TMonoProtocol, obj: Dict):
        return cls(
            protocol,
            obj.get("memberName"),
            obj.get("permission"),
            obj.get("id"),
            obj.get("specialTitle"),
            obj.get("joinTimestamp"),
            obj.get("lastSpeakTimestamp"),
            obj.get("mutetimeRemaining")
        )

    def avatar(self):
        return f'https://q4.qlogo.cn/g?b=qq&nk={self.metadata.identifier}&s=140'

    @property
    def group(self):
        return list(self.parents.values())[0]


class Group(Monomer):
    prefab_metadata = GroupData
    prefab_behavior = MessageBehavior

    def __init__(
            self,
            protocol: TMonoProtocol,
            name: str,
            permission: str,
            identifier: Optional[int] = None,
    ):
        super().__init__(protocol, name, identifier)
        self.metadata.permission = Permission(permission)
