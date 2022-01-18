from enum import Enum
from arclet.cesloi.event.messages import *
from arclet.cesloi.event.mirai import *


class MType(Enum):
    ALL = Message
    Friend = FriendMessage
    Group = GroupMessage
    Temp = TempMessage
    Stranger = StrangerMessage
    Client = OtherClientMessage


class RType(Enum):
    ALL = RequestEvent
    NewFriend = NewFriendRequestEvent
    MemberJoin = MemberJoinRequestEvent
    BotInvited = BotInvitedJoinGroupRequestEvent


class _NBot(Enum):
    ALL = BotEvent
    Online = BotOnlineEvent
    OfflineActive = BotOfflineEventActive
    OfflineForce = BotOfflineEventForce
    OfflineDropped = BotOfflineEventDropped
    Relogin = BotReloginEvent


class _NFriend(Enum):
    ALL = FriendEvent
    InputStatusChanged = FriendInputStatusChangedEvent
    NickChanged = FriendNickChangedEvent
    Recall = FriendRecallEvent


class _NGroup(Enum):
    ALL = GroupEvent
    BotPermissionChange = BotGroupPermissionChangeEvent


class NType:
    Bot = _NBot
    Friend = _NFriend
    Group = _NGroup