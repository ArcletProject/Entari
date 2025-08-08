from __future__ import annotations

from collections.abc import Awaitable, Iterable
from typing import Callable, Generic, NoReturn, TypeVar, cast, overload

from arclet.letoderea import STOP, es, step_out
from satori import ChannelType
from satori.client.account import Account
from satori.client.protocol import ApiProtocol
from satori.const import Api
from satori.element import Element
from satori.model import Channel, Guild, Member, MessageReceipt, PageResult, Role, User

from .event.base import (
    FriendRequestEvent,
    GuildMemberRequestEvent,
    GuildRequestEvent,
    MessageCreatedEvent,
    MessageEvent,
    Reply,
    SatoriEvent,
)
from .event.send import SendRequest, SendResponse
from .message import MessageChain

TEvent = TypeVar("TEvent", bound=SatoriEvent)
T = TypeVar("T")


class EntariProtocol(ApiProtocol):

    async def send_message(
        self, channel: str | Channel, message: str | Iterable[str | Element], source: SatoriEvent | None = None
    ) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            channel (str | Channel): 要发送的频道 ID
            message (str | Iterable[str | Element]): 要发送的消息
            source (SatoriEvent | None): 源事件

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        channel_id = channel.id if isinstance(channel, Channel) else channel
        return await self.message_create(channel_id=channel_id, content=message, source=source)

    async def send_private_message(
        self, user: str | User, message: str | Iterable[str | Element], source: SatoriEvent | None = None
    ) -> list[MessageReceipt]:
        """发送私聊消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            user (str | User): 要发送的用户 ID
            message (str | Iterable[str | Element]): 要发送的消息
            source (SatoriEvent | None): 源事件

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        user_id = user.id if isinstance(user, User) else user
        channel = await self.user_channel_create(user_id=user_id)
        return await self.message_create(channel_id=channel.id, content=message, source=source)

    async def message_create(
        self, channel_id: str, content: str | Iterable[str | Element], source: SatoriEvent | None = None
    ) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            channel_id (str): 频道 ID
            content (str | Iterable[str | Element]): 消息内容
            source (SatoriEvent | None): 源事件

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        msg = MessageChain(content)
        sess = None
        if source:
            sess = Session(self.account, source)
            sess.elements = msg
        if res := await es.post(SendRequest(self.account, channel_id, msg, sess)):
            if not res.value:
                return []
            elif res.value is True:
                pass
            else:
                msg = res.value
        send = str(msg)
        res = await self.call_api(
            Api.MESSAGE_CREATE,
            {"channel_id": channel_id, "content": send},
        )
        res = cast("list[dict]", res)
        resp = [MessageReceipt.parse(i) for i in res]
        await es.publish(SendResponse(self.account, channel_id, msg, resp, sess))
        return resp


class Session(Generic[TEvent]):
    """在 Satori-Python 的 Session 的基础上存储了当次事件的信息"""

    def __init__(self, account: Account[EntariProtocol], event: TEvent):
        self.account = account
        self.event = event
        self.type = event.type
        self._content = None
        if isinstance(event, MessageEvent):
            self._content = MessageChain(event.message.message)
        self.reply: Reply | None = None

    @overload
    async def prompt(
        self,
        message: str | Iterable[str | Element] | None = None,
        /,
        *,
        timeout: float = 120,
        timeout_message: str | Iterable[str | Element] = "等待超时",
    ) -> MessageChain | None:
        """等待当前会话的下一次输入并返回

        Args:
            message: 等待前用于提示的消息
            timeout: 等待超时时间
            timeout_message: 超时后发送的消息

        Returns:
            MessageChain | None: 回复的消息，若超时则返回 None
        """
        ...

    @overload
    async def prompt(
        self,
        handler: Callable[..., Awaitable[T]],
        message: str | Iterable[str | Element] | None = None,
        /,
        *,
        timeout: float = 120,
        timeout_message: str | Iterable[str | Element] = "等待超时",
    ) -> T | None:
        """处理当前会话的下一次输入并返回

        Args:
            handler: 用于处理输入的函数
            message: 等待前用于提示的消息
            timeout: 等待超时时间
            timeout_message: 超时后发送的消息

        Returns:
            T | None: 回复的内容，若超时则返回 None
        """
        ...

    async def prompt(
        self,
        *args,
        timeout: float = 120,
        timeout_message: str | Iterable[str | Element] = "等待超时",
    ):
        if not args:
            handler, message = None, None
        elif len(args) == 1:
            if callable(args[0]):
                handler, message = args[0], None
            else:
                handler, message = None, args[0]
        else:
            handler, message = args[0], args[1]
        if message:
            await self.send(message)

        if handler:
            step = step_out(MessageCreatedEvent, handler)
        else:

            async def waiter(content: MessageChain, session: Session[MessageCreatedEvent]):
                if self.event.user and self.event.user.id == session.event.user.id:
                    if session.event.channel.type == ChannelType.DIRECT:
                        return content
                    if self.event.channel and session.event.channel.id == self.event.channel.id:
                        return content

            waiter.__annotations__ = {"content": MessageChain, "session": self.__class__}

            step = step_out(MessageCreatedEvent, waiter)

        result = await step.wait(timeout=timeout)
        if result is None:
            await self.send(timeout_message)
            return None
        return result

    def stop(self) -> NoReturn:
        raise STOP

    @property
    def quote(self):
        if isinstance(self.event, MessageEvent):
            return self.event.quote
        return None

    @property
    def user(self) -> User:
        if not self.event.user:
            raise RuntimeError(f"Event {self.event.type!r} has no User")
        return self.event.user

    @property
    def guild(self) -> Guild:
        if not self.event.guild:
            raise RuntimeError(f"Event {self.event.type!r} has no Guild")
        return self.event.guild

    @property
    def channel(self) -> Channel:
        if not self.event.channel:
            raise RuntimeError(f"Event {self.event.type!r} has no Channel")
        return self.event.channel

    @property
    def member(self) -> Member:
        if not self.event.member:
            raise RuntimeError(f"Event {self.event.type!r} has no Member")
        return self.event.member

    @property
    def content(self) -> str:
        if self._content:
            return str(self._content)
        raise RuntimeError(f"Event {self.event.type!r} has no Content")

    @content.setter
    def content(self, value: str):
        self._content = MessageChain(value)

    @property
    def elements(self) -> MessageChain:
        if self._content:
            return self._content
        raise RuntimeError(f"Event {self.event.type!r} has no Content")

    @elements.setter
    def elements(self, value: MessageChain):
        self._content = value

    async def _send(self, channel_id: str, message: str | Iterable[str | Element]):
        return await self.account.protocol.send_message(channel_id, message, self.event)

    async def send(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageReceipt]:
        if not self.event._origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.send_message(self.event._origin.channel.id, message, self.event)

    async def send_message(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageReceipt]:
        """发送消息

        Args:
            message: 要发送的消息
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.send_message(self.event.channel.id, message, self.event)

    async def send_private_message(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageReceipt]:
        """发送私聊消息

        Args:
            message: 要发送的消息
        """
        channel = await self.user_channel_create()
        return await self.account.protocol.send_message(channel.id, message, self.event)

    async def update_message(
        self,
        message: str | Iterable[str | Element],
    ):
        """更新消息

        Args:
            message: 要更新的消息
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.event.message:
            raise RuntimeError("Event cannot update message")
        return await self.account.protocol.update_message(self.event.channel, self.event.message.id, message)

    async def message_create(
        self,
        content: str,
    ) -> list[MessageReceipt]:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.send_message(self.event.channel.id, content, self.event)

    async def message_delete(self, message_id: str) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        await self.account.protocol.message_delete(
            self.event.channel.id,
            message_id,
        )

    async def message_update(
        self,
        content: str,
    ) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.event.message:
            raise RuntimeError("Event cannot update message")
        await self.account.protocol.message_update(
            self.event.channel.id,
            self.event.message.id,
            content,
        )

    async def channel_create(self, data: Channel) -> Channel:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to create channel!")
        return await self.account.protocol.channel_create(self.event.guild.id, data)

    async def channel_list(self, next_token: str | None = None) -> PageResult[Channel]:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to list channel!")
        return await self.account.protocol.channel_list(self.event.guild.id, next_token)

    async def channel_update(
        self,
        data: Channel,
    ) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot use to update channel!")
        return await self.account.protocol.channel_update(self.event.channel.id, data)

    async def channel_delete(self) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot use to delete channel!")
        return await self.account.protocol.channel_delete(
            self.event.channel.id,
        )

    async def user_channel_create(self) -> Channel:
        if not self.event.user:
            raise RuntimeError("Event cannot use to create user channel!")
        return await self.account.protocol.user_channel_create(
            self.event.user.id, self.event.guild.id if self.event.guild else None
        )

    async def guild_member_list(self, next_token: str | None = None) -> PageResult[Member]:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to list member!")
        return await self.account.protocol.guild_member_list(self.event.guild.id, next_token)

    async def guild_member_get(self, user_id: str | None = None) -> Member:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to get member!")
        if user_id:
            return await self.account.protocol.guild_member_get(self.event.guild.id, user_id)
        if not self.event.user:
            raise RuntimeError("Event cannot use to get member!")
        return await self.account.protocol.guild_member_get(self.event.guild.id, self.event.user.id)

    async def guild_member_kick(self, user_id: str | None = None, permanent: bool = False) -> None:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to kick member!")
        if user_id:
            return await self.account.protocol.guild_member_kick(self.event.guild.id, user_id, permanent)
        if not self.event.user:
            raise RuntimeError("Event cannot use to kick member!")
        return await self.account.protocol.guild_member_kick(self.event.guild.id, self.event.user.id, permanent)

    async def guild_member_role_set(self, role_id: str, user_id: str | None = None) -> None:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to guild member role set!")
        if user_id:
            return await self.account.protocol.guild_member_role_set(self.event.guild.id, user_id, role_id)
        if not self.event.user:
            raise RuntimeError("Event cannot use to guild member role set!")
        return await self.account.protocol.guild_member_role_set(self.event.guild.id, self.event.user.id, role_id)

    async def guild_member_role_unset(self, role_id: str, user_id: str | None = None) -> None:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to guild member role unset!")
        if user_id:
            return await self.account.protocol.guild_member_role_unset(self.event.guild.id, user_id, role_id)
        if not self.event.user:
            raise RuntimeError("Event cannot use to guild member role unset!")
        return await self.account.protocol.guild_member_role_unset(self.event.guild.id, self.event.user.id, role_id)

    async def guild_role_list(self, next_token: str | None = None) -> PageResult[Role]:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to list role!")
        return await self.account.protocol.guild_role_list(self.event.guild.id, next_token)

    async def guild_role_create(
        self,
        role: Role,
    ) -> Role:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to create role!")
        return await self.account.protocol.guild_role_create(self.event.guild.id, role)

    async def guild_role_update(
        self,
        role_id: str,
        role: Role,
    ) -> None:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to update role!")
        return await self.account.protocol.guild_role_update(self.event.guild.id, role_id, role)

    async def guild_role_delete(self, role_id: str) -> None:
        if not self.event.guild:
            raise RuntimeError("Event cannot use to delete role!")
        return await self.account.protocol.guild_role_delete(
            self.event.guild.id,
            role_id,
        )

    async def reaction_create(
        self,
        emoji: str,
    ) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.event.message:
            raise RuntimeError("Event cannot create reaction")
        return await self.account.protocol.reaction_create(self.event.channel.id, self.event.message.id, emoji)

    async def reaction_delete(
        self,
        emoji: str,
        user_id: str | None = None,
    ) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.event.message:
            raise RuntimeError("Event cannot delete reaction")
        return await self.account.protocol.reaction_delete(self.event.channel.id, self.event.message.id, emoji, user_id)

    async def reaction_clear(
        self,
        emoji: str | None = None,
    ) -> None:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.event.message:
            raise RuntimeError("Event cannot clear reaction")
        return await self.account.protocol.reaction_clear(
            self.event.channel.id,
            self.event.message.id,
            emoji,
        )

    async def reaction_list(
        self,
        emoji: str,
        next_token: str | None = None,
    ) -> PageResult[User]:
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.event.message:
            raise RuntimeError("Event cannot list reaction")
        return await self.account.protocol.reaction_list(
            self.event.channel.id, self.event.message.id, emoji, next_token
        )

    async def request_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if isinstance(self.event, FriendRequestEvent):
            return await self.friend_approve(approve, comment)
        if isinstance(self.event, GuildRequestEvent):
            return await self.guild_approve(approve, comment)
        if isinstance(self.event, GuildMemberRequestEvent):
            return await self.guild_member_approve(approve, comment)
        raise RuntimeError("Event cannot approve request")

    async def friend_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if not isinstance(self.event, FriendRequestEvent):
            raise RuntimeError("Event cannot approve friend request")
        return await self.account.protocol.friend_approve(self.event.message.id, approve, comment)

    async def guild_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if not isinstance(self.event, GuildRequestEvent):
            raise RuntimeError("Event cannot approve guild request")
        return await self.account.protocol.guild_approve(self.event.message.id, approve, comment)

    async def guild_member_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if not isinstance(self.event, GuildMemberRequestEvent):
            raise RuntimeError("Event cannot approve guild member request")
        return await self.account.protocol.guild_member_approve(self.event.message.id, approve, comment)
