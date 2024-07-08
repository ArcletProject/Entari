from __future__ import annotations

from collections.abc import Iterable
from typing import Generic, NoReturn, TypeVar

from arclet.letoderea import ParsingStop, StepOut
from satori.client.account import Account
from satori.element import Element
from satori.model import Channel, Guild, Member, MessageObject, PageResult, Role, User

from .event import Event, FriendRequestEvent, GuildMemberRequestEvent, GuildRequestEvent, MessageEvent
from .message import MessageChain

TEvent = TypeVar("TEvent", bound=Event)


class Session(Generic[TEvent]):
    """在 Satori-Python 的 Session 的基础上存储了当次事件的信息"""

    def __init__(self, account: Account, event: TEvent):
        self.account = account
        self.context = event
        self.origin = event._origin
        self._content = None
        if isinstance(event, MessageEvent):
            self._content = MessageChain(event.message.message)

    async def prompt(
        self,
        message: str | Iterable[str | Element],
        timeout: float = 120,
        timeout_message: str | Iterable[str | Element] = "等待超时",
        keep_sender: bool = True,
    ) -> MessageChain:
        """发送提示消息, 并等待回复

        Args:
            message: 要发送的消息
            timeout: 等待超时时间
            timeout_message: 超时后发送的消息
            keep_sender: 是否只允许原发送者回复
        """
        await self.send(message)

        async def waiter(content: MessageChain, session: Session[MessageEvent]):
            if self.origin.channel:
                if self.origin.channel.id == session.context.channel.id and (
                    not keep_sender
                    or (
                        self.origin.user
                        and session.context.user
                        and self.origin.user.id == session.context.user.id
                    )
                ):
                    return content
            elif self.origin.user:
                if self.origin.user.id == session.context.user.id:
                    return content

        waiter.__annotations__ = {"content": MessageChain, "session": self.__class__}

        step = StepOut([MessageEvent], waiter)

        result = await step.wait(timeout=timeout)
        if not result:
            await self.send(timeout_message)
            raise ParsingStop()
        return result

    def stop(self) -> NoReturn:
        raise ParsingStop()

    @property
    def user(self) -> User:
        if not self.origin.user:
            raise RuntimeError(f"Event {self.origin.type!r} has no User")
        return self.origin.user

    @property
    def guild(self) -> Guild:
        if not self.origin.guild:
            raise RuntimeError(f"Event {self.origin.type!r} has no Guild")
        return self.origin.guild

    @property
    def channel(self) -> Channel:
        if not self.origin.channel:
            raise RuntimeError(f"Event {self.origin.type!r} has no Channel")
        return self.origin.channel

    @property
    def member(self) -> Member:
        if not self.origin.member:
            raise RuntimeError(f"Event {self.origin.type!r} has no Member")
        return self.origin.member

    @property
    def content(self) -> str:
        if self._content:
            return str(self._content)
        raise RuntimeError(f"Event {self.origin.type!r} has no Content")

    @content.setter
    def content(self, value: str):
        self._content = MessageChain(value)

    @property
    def elements(self) -> MessageChain:
        if self._content:
            return self._content
        raise RuntimeError(f"Event {self.origin.type!r} has no Content")

    def __getattr__(self, item):
        return getattr(self.account.protocol, item)

    async def send(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        return await self.account.protocol.send(self.origin, message)

    async def send_message(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送消息

        Args:
            message: 要发送的消息
        """
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.send_message(self.origin.channel, message)

    async def send_private_message(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送私聊消息

        Args:
            message: 要发送的消息
        """
        if not self.origin.user:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.send_private_message(self.origin.user, message)

    async def update_message(
        self,
        message: str | Iterable[str | Element],
    ):
        """更新消息

        Args:
            message: 要更新的消息
        """
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot update message")
        return await self.account.protocol.update_message(
            self.origin.channel, self.origin.message.id, message
        )

    async def message_create(
        self,
        content: str,
    ) -> list[MessageObject]:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.message_create(self.origin.channel.id, content)

    async def message_delete(self) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot update message")
        await self.account.protocol.message_delete(
            self.origin.channel.id,
            self.origin.message.id,
        )

    async def message_update(
        self,
        content: str,
    ) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot update message")
        await self.account.protocol.message_update(
            self.origin.channel.id,
            self.origin.message.id,
            content,
        )

    async def channel_create(self, data: Channel) -> Channel:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to create channel!")
        return await self.account.protocol.channel_create(self.origin.guild.id, data)

    async def channel_list(self, next_token: str | None = None) -> PageResult[Channel]:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to list channel!")
        return await self.account.protocol.channel_list(self.origin.guild.id, next_token)

    async def channel_update(
        self,
        data: Channel,
    ) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot use to update channel!")
        return await self.account.protocol.channel_update(self.origin.channel.id, data)

    async def channel_delete(self) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot use to delete channel!")
        return await self.account.protocol.channel_delete(
            self.origin.channel.id,
        )

    async def user_channel_create(self) -> Channel:
        if not self.origin.user:
            raise RuntimeError("Event cannot use to create user channel!")
        return await self.account.protocol.user_channel_create(
            self.origin.user.id, self.origin.guild.id if self.origin.guild else None
        )

    async def guild_member_list(self, next_token: str | None = None) -> PageResult[Member]:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to list member!")
        return await self.account.protocol.guild_member_list(self.origin.guild.id, next_token)

    async def guild_member_get(self, user_id: str | None = None) -> Member:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to get member!")
        if user_id:
            return await self.account.protocol.guild_member_get(self.origin.guild.id, user_id)
        if not self.origin.user:
            raise RuntimeError("Event cannot use to get member!")
        return await self.account.protocol.guild_member_get(self.origin.guild.id, self.origin.user.id)

    async def guild_member_kick(self, user_id: str | None = None, permanent: bool = False) -> None:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to kick member!")
        if user_id:
            return await self.account.protocol.guild_member_kick(self.origin.guild.id, user_id, permanent)
        if not self.origin.user:
            raise RuntimeError("Event cannot use to kick member!")
        return await self.account.protocol.guild_member_kick(
            self.origin.guild.id, self.origin.user.id, permanent
        )

    async def guild_member_role_set(self, role_id: str, user_id: str | None = None) -> None:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to guild member role set!")
        if user_id:
            return await self.account.protocol.guild_member_role_set(self.origin.guild.id, user_id, role_id)
        if not self.origin.user:
            raise RuntimeError("Event cannot use to guild member role set!")
        return await self.account.protocol.guild_member_role_set(
            self.origin.guild.id, self.origin.user.id, role_id
        )

    async def guild_member_role_unset(self, role_id: str, user_id: str | None = None) -> None:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to guild member role unset!")
        if user_id:
            return await self.account.protocol.guild_member_role_unset(self.origin.guild.id, user_id, role_id)
        if not self.origin.user:
            raise RuntimeError("Event cannot use to guild member role unset!")
        return await self.account.protocol.guild_member_role_unset(
            self.origin.guild.id, self.origin.user.id, role_id
        )

    async def guild_role_list(self, next_token: str | None = None) -> PageResult[Role]:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to list role!")
        return await self.account.protocol.guild_role_list(self.origin.guild.id, next_token)

    async def guild_role_create(
        self,
        role: Role,
    ) -> Role:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to create role!")
        return await self.account.protocol.guild_role_create(self.origin.guild.id, role)

    async def guild_role_update(
        self,
        role_id: str,
        role: Role,
    ) -> None:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to update role!")
        return await self.account.protocol.guild_role_update(self.origin.guild.id, role_id, role)

    async def guild_role_delete(self, role_id: str) -> None:
        if not self.origin.guild:
            raise RuntimeError("Event cannot use to delete role!")
        return await self.account.protocol.guild_role_delete(
            self.origin.guild.id,
            role_id,
        )

    async def reaction_create(
        self,
        emoji: str,
    ) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot create reaction")
        return await self.account.protocol.reaction_create(
            self.origin.channel.id, self.origin.message.id, emoji
        )

    async def reaction_delete(
        self,
        emoji: str,
        user_id: str | None = None,
    ) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot delete reaction")
        return await self.account.protocol.reaction_delete(
            self.origin.channel.id, self.origin.message.id, emoji, user_id
        )

    async def reaction_clear(
        self,
        emoji: str | None = None,
    ) -> None:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot clear reaction")
        return await self.account.protocol.reaction_clear(
            self.origin.channel.id,
            self.origin.message.id,
            emoji,
        )

    async def reaction_list(
        self,
        emoji: str,
        next_token: str | None = None,
    ) -> PageResult[User]:
        if not self.origin.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.origin.message:
            raise RuntimeError("Event cannot list reaction")
        return await self.account.protocol.reaction_list(
            self.origin.channel.id, self.origin.message.id, emoji, next_token
        )

    async def request_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if isinstance(self.context, FriendRequestEvent):
            return await self.friend_approve(approve, comment)
        if isinstance(self.context, GuildRequestEvent):
            return await self.guild_approve(approve, comment)
        if isinstance(self.context, GuildMemberRequestEvent):
            return await self.guild_member_approve(approve, comment)
        raise RuntimeError("Event cannot approve request")

    async def friend_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if not isinstance(self.context, FriendRequestEvent):
            raise RuntimeError("Event cannot approve friend request")
        return await self.account.protocol.friend_approve(self.context.message.id, approve, comment)

    async def guild_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if not isinstance(self.context, GuildRequestEvent):
            raise RuntimeError("Event cannot approve guild request")
        return await self.account.protocol.guild_approve(self.context.message.id, approve, comment)

    async def guild_member_approve(
        self,
        approve: bool,
        comment: str,
    ):
        if not isinstance(self.context, GuildMemberRequestEvent):
            raise RuntimeError("Event cannot approve guild member request")
        return await self.account.protocol.guild_member_approve(self.context.message.id, approve, comment)
