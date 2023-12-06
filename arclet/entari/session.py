from __future__ import annotations

from collections.abc import Iterable

from satori.client.account import Account
from satori.element import Element
from satori.model import Channel, Event, Member, MessageObject, PageResult, Role, User


class ContextSession:
    """在 Satori-Python 的 Session 的基础上存储了当次事件的信息"""

    def __init__(self, account: Account, event: Event):
        self.account = account
        self.context = event

    def __getattr__(self, item):
        return getattr(self.account.session, item)

    async def send(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        return await self.account.session.send(self.context, message)

    async def send_message(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送消息

        参数:
            message: 要发送的消息
        """
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.session.send_message(self.context.channel, message)

    async def send_private_message(
        self,
        message: str | Iterable[str | Element],
    ) -> list[MessageObject]:
        """发送私聊消息

        参数:
            message: 要发送的消息
        """
        if not self.context.user:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.session.send_private_message(self.context.user, message)

    async def update_message(
        self,
        message: str | Iterable[str | Element],
    ):
        """更新消息

        参数:
            message: 要更新的消息
        """
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot update message")
        return await self.account.session.update_message(
            self.context.channel, self.context.message.id, message
        )

    async def message_create(
        self,
        content: str,
    ) -> list[MessageObject]:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.session.message_create(self.context.channel.id, content)

    async def message_delete(self) -> None:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot update message")
        await self.account.session.message_delete(
            self.context.channel.id,
            self.context.message.id,
        )

    async def message_update(
        self,
        content: str,
    ) -> None:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot update message")
        await self.account.session.message_update(
            self.context.channel.id,
            self.context.message.id,
            content,
        )

    async def channel_create(self, data: Channel) -> Channel:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to create channel!")
        return await self.account.session.channel_create(self.context.guild.id, data)

    async def channel_list(self, next_token: str | None = None) -> PageResult[Channel]:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to list channel!")
        return await self.account.session.channel_list(self.context.guild.id, next_token)

    async def channel_update(
        self,
        data: Channel,
    ) -> None:
        if not self.context.channel:
            raise RuntimeError("Event cannot use to update channel!")
        return await self.account.session.channel_update(self.context.channel.id, data)

    async def channel_delete(self) -> None:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to delete channel!")
        return await self.account.session.channel_delete(
            self.context.channel.id,
        )

    async def user_channel_create(self) -> Channel:
        if not self.context.user:
            raise RuntimeError("Event cannot use to create user channel!")
        return await self.account.session.user_channel_create(
            self.context.user.id, self.context.guild.id if self.context.guild else None
        )

    async def guild_member_list(self, next_token: str | None = None) -> PageResult[Member]:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to list member!")
        return await self.account.session.guild_member_list(self.context.guild.id, next_token)

    async def guild_member_get(self, user_id: str | None = None) -> Member:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to get member!")
        if user_id:
            return await self.account.session.guild_member_get(self.context.guild.id, user_id)
        if not self.context.user:
            raise RuntimeError("Event cannot use to get member!")
        return await self.account.session.guild_member_get(self.context.guild.id, self.context.user.id)

    async def guild_member_kick(self, user_id: str | None = None, permanent: bool = False) -> None:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to kick member!")
        if user_id:
            return await self.account.session.guild_member_kick(self.context.guild.id, user_id, permanent)
        if not self.context.user:
            raise RuntimeError("Event cannot use to kick member!")
        return await self.account.session.guild_member_kick(
            self.context.guild.id, self.context.user.id, permanent
        )

    async def guild_member_role_set(self, role_id: str, user_id: str | None = None) -> None:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to guild member role set!")
        if user_id:
            return await self.account.session.guild_member_role_set(self.context.guild.id, user_id, role_id)
        if not self.context.user:
            raise RuntimeError("Event cannot use to guild member role set!")
        return await self.account.session.guild_member_role_set(
            self.context.guild.id, self.context.user.id, role_id
        )

    async def guild_member_role_unset(self, role_id: str, user_id: str | None = None) -> None:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to guild member role unset!")
        if user_id:
            return await self.account.session.guild_member_role_unset(self.context.guild.id, user_id, role_id)
        if not self.context.user:
            raise RuntimeError("Event cannot use to guild member role unset!")
        return await self.account.session.guild_member_role_unset(
            self.context.guild.id, self.context.user.id, role_id
        )

    async def guild_role_list(self, next_token: str | None = None) -> PageResult[Role]:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to list role!")
        return await self.account.session.guild_role_list(self.context.guild.id, next_token)

    async def guild_role_create(
        self,
        role: Role,
    ) -> Role:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to create role!")
        return await self.account.session.guild_role_create(self.context.guild.id, role)

    async def guild_role_update(
        self,
        role_id: str,
        role: Role,
    ) -> None:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to update role!")
        return await self.account.session.guild_role_update(self.context.guild.id, role_id, role)

    async def guild_role_delete(self, role_id: str) -> None:
        if not self.context.guild:
            raise RuntimeError("Event cannot use to delete role!")
        return await self.account.session.guild_role_delete(
            self.context.guild.id,
            role_id,
        )

    async def reaction_create(
        self,
        emoji: str,
    ) -> None:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot create reaction")
        return await self.account.session.reaction_create(
            self.context.channel.id, self.context.message.id, emoji
        )

    async def reaction_delete(
        self,
        emoji: str,
        user_id: str | None = None,
    ) -> None:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot delete reaction")
        return await self.account.session.reaction_delete(
            self.context.channel.id, self.context.message.id, emoji, user_id
        )

    async def reaction_clear(
        self,
        emoji: str | None = None,
    ) -> None:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot clear reaction")
        return await self.account.session.reaction_clear(
            self.context.channel.id,
            self.context.message.id,
            emoji,
        )

    async def reaction_list(
        self,
        emoji: str,
        next_token: str | None = None,
    ) -> PageResult[User]:
        if not self.context.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not self.context.message:
            raise RuntimeError("Event cannot list reaction")
        return await self.account.session.reaction_list(
            self.context.channel.id, self.context.message.id, emoji, next_token
        )
