import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Generic, NoReturn, cast, overload
from typing_extensions import TypeVar

from arclet.letoderea import STOP, es, step_out
from satori import ChannelType, Quote
from satori.client.account import Account
from satori.client.protocol import ApiProtocol
from satori.const import Api
from satori.element import At, Element
from satori.model import (
    Channel,
    Guild,
    IterablePageResult,
    Login,
    Member,
    MessageObject,
    MessageReceipt,
    Meta,
    Role,
    Upload,
    User,
)

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

TEvent = TypeVar("TEvent", bound=SatoriEvent, default=SatoriEvent)
T = TypeVar("T")


class EntariProtocol(ApiProtocol):
    # fmt: off

    async def send_message(self, channel: str | Channel, message: str | Iterable[str | Element], source: SatoriEvent | None = None, at_sender: At | None = None, reply_to: Quote | None = None) -> list[MessageReceipt]:  # noqa: E501
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            channel (str | Channel): 要发送的频道 ID
            message (str | Iterable[str | Element]): 要发送的消息
            source (SatoriEvent | None): 源事件
            at_sender (At | None): 是否 @ 发送者，默认为 None
            reply_to (Quote | None): 是否作为回复发送，默认为 None

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        channel_id = channel.id if isinstance(channel, Channel) else channel
        return await self.message_create(channel_id=channel_id, content=message, source=source, at_sender=at_sender, reply_to=reply_to)  # noqa: E501

    async def send_private_message(self, user: str | User, message: str | Iterable[str | Element], source: SatoriEvent | None = None, at_sender: At | None = None, reply_to: Quote | None = None) -> list[MessageReceipt]:  # noqa: E501
        """发送私聊消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            user (str | User): 要发送的用户 ID
            message (str | Iterable[str | Element]): 要发送的消息
            source (SatoriEvent | None): 源事件
            at_sender (At | None): 是否 @ 发送者，默认为 None
            reply_to (Quote | None): 是否作为回复发送，默认为 None

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        user_id = user.id if isinstance(user, User) else user
        channel = await self.user_channel_create(user_id=user_id)
        return await self.message_create(channel_id=channel.id, content=message, source=source, at_sender=at_sender, reply_to=reply_to)  # noqa: E501

    async def message_create(self, channel_id: str, content: str | Iterable[str | Element], source: SatoriEvent | None = None, at_sender: At | None = None, reply_to: Quote | None = None) -> list[MessageReceipt]:  # noqa: E501
        """发送消息。返回一个 `MessageReceipt` 对象构成的数组。

        Args:
            channel_id (str): 频道 ID
            content (str | Iterable[str | Element]): 消息内容
            source (SatoriEvent | None): 源事件
            at_sender (At | None): 是否 @ 发送者，默认为 None
            reply_to (Quote | None): 是否作为回复发送，默认为 None

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        msg: MessageChain = MessageChain.of(content) if isinstance(content, str) else MessageChain(content)
        if at_sender:
            msg.insert(0, at_sender)
        if reply_to:
            msg.insert(0, reply_to)
        sess = None
        if source:
            sess = Session(self.account.custom(protocol_cls=EntariProtocol), source)
            sess.elements = msg
        res = await es.post(ev := SendRequest(self.account.custom(protocol_cls=EntariProtocol), channel_id, msg, sess))
        msg = sess._content if sess and sess._content else ev.message
        if res:
            if res.value is False:
                return []
            elif isinstance(res.value, MessageChain):
                msg = res.value
        send = str(msg)
        res = await self.call_api(
            Api.MESSAGE_CREATE,
            {"channel_id": channel_id, "content": send},
        )
        res = cast("list[dict]", res)
        resp = [MessageReceipt.parse(i) for i in res]
        await es.publish(SendResponse(self.account.custom(protocol_cls=EntariProtocol), channel_id, msg, resp, sess))
        return resp

    # fmt: on


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
        block: bool = True,
    ) -> MessageChain | None:
        """等待当前会话的下一次输入并返回

        Args:
            message: 等待前用于提示的消息
            timeout: 等待超时时间
            timeout_message: 超时后发送的消息
            block: 是否阻塞后续的消息传递

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
        block: bool = True,
    ) -> T | None:
        """处理当前会话的下一次输入并返回

        Args:
            handler: 用于处理输入的函数
            message: 等待前用于提示的消息
            timeout: 等待超时时间
            timeout_message: 超时后发送的消息
            block: 是否阻塞后续的消息传递

        Returns:
            T | None: 回复的内容，若超时则返回 None
        """
        ...

    async def prompt(
        self,
        *args,
        timeout: float = 120,
        timeout_message: str | Iterable[str | Element] = "等待超时",
        block: bool = True,
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
            step = step_out(MessageCreatedEvent, handler, block=block)
        else:

            async def waiter(content: MessageChain, session: Session[MessageCreatedEvent]):
                if self.event.user and self.event.user.id == session.event.user.id:
                    if session.event.channel.type == ChannelType.DIRECT:
                        return content
                    if self.event.channel and session.event.channel.id == self.event.channel.id:
                        return content

            waiter.__annotations__ = {"content": MessageChain, "session": self.__class__}

            step = step_out(MessageCreatedEvent, waiter, block=block)

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

    def _resolve(self, at_sender: bool, reply_to: bool):
        at = reply = None
        if at_sender:
            if not self.event.user:
                raise RuntimeError("Event has no User to @!")
            at = At(self.event.user.id)
        if reply_to:
            if not isinstance(self.event, MessageEvent):
                raise RuntimeError("Event cannot be replied to!")
            if not self.event.message:
                raise RuntimeError("Event cannot be replied to!")
            reply = Quote(self.event.message.id)
        return at, reply

    # fmt: off

    async def send(self, message: str | Iterable[str | Element], at_sender: bool = False, reply_to: bool = False) -> list[MessageReceipt]:  # noqa: E501
        """发送消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            message: 要发送的消息
            at_sender: 是否 @ 发送者，默认为 False
            reply_to: 是否作为回复发送，默认为 False

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        if not self.event._origin.channel:
            raise RuntimeError("Event has no Channel context!")
        return await self.account.protocol.send_message(self.event._origin.channel.id, message, self.event, *self._resolve(at_sender, reply_to))  # noqa: E501

    async def send_message(self, message: str | Iterable[str | Element], at_sender: bool = False, reply_to: bool = False) -> list[MessageReceipt]:  # noqa: E501
        """发送消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            message: 要发送的消息
            at_sender: 是否 @ 发送者，默认为 False
            reply_to: 是否作为回复发送，默认为 False

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        if not self.event.channel:
            raise RuntimeError("Event has no Channel context!")
        return await self.account.protocol.send_message(self.event.channel.id, message, self.event, *self._resolve(at_sender, reply_to))  # noqa: E501

    async def send_private_message(self, message: str | Iterable[str | Element], user_id: str | None = None, at_sender: bool = False, reply_to: bool = False) -> list[MessageReceipt]:  # noqa: E501
        """发送私聊消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            message: 要发送的消息
            user_id: 要发送的用户 ID，默认为 None（即发送给当前事件的用户）
            at_sender: 是否 @ 发送者，默认为 False
            reply_to: 是否作为回复发送，默认为 False

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        channel = await self.user_channel_create(user_id)
        return await self.account.protocol.send_message(channel.id, message, self.event, *self._resolve(at_sender, reply_to))  # noqa: E501

    # fmt: on

    async def update_message(self, message: str | Iterable[str | Element]):
        """更新消息。

        Args:
            message (str | Iterable[str | Element]): 更新后的消息

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event has no Channel context!")
        if not self.event.message:
            raise RuntimeError("Event cannot update message")
        return await self.account.protocol.update_message(self.event.channel, self.event.message.id, message)

    async def message_create(self, content: str) -> list[MessageReceipt]:
        """发送消息。返回一个 `MessageObject` 对象构成的数组。

        Args:
            content (str): 消息内容

        Returns:
            list[MessageReceipt]: `MessageReceipt` 对象构成的数组
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        return await self.account.protocol.message_create(self.event.channel.id, content, self.event)

    async def message_get(self, message_id: str) -> MessageObject:
        """获取特定消息。返回一个 `MessageObject` 对象。

        Args:
            message_id (str): 消息 ID

        Returns:
            MessageObject: `MessageObject` 对象
        """
        if not self.event.channel:
            raise RuntimeError("Event has no Channel context!")
        return await self.account.protocol.message_get(self.event.channel.id, message_id)

    async def message_delete(self, message_id: str, delay: float = -1) -> None:
        """撤回特定消息。

        Args:
            message_id (str): 消息 ID
            delay (float, optional): 延迟撤回时间，单位为秒，默认为 -1（表示不延迟）

        Returns:
            None: 该方法无返回值
        """
        if delay > 0:
            await asyncio.sleep(delay)
        if not self.event.channel:
            raise RuntimeError("Event has no Channel context!")
        await self.account.protocol.message_delete(self.event.channel.id, message_id)

    async def message_update(self, content: str) -> None:
        """编辑特定消息。

        Args:
            content (str): 消息内容

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event has no Channel context!")
        if not self.event.message:
            raise RuntimeError("Event cannot update message")
        await self.account.protocol.message_update(
            self.event.channel.id,
            self.event.message.id,
            content,
        )

    async def channel_create(self, data: Channel) -> Channel:
        """创建群组频道。返回一个 Channel 对象。

        Args:
            data (Channel): 频道数据

        Returns:
            Channel: `Channel` 对象
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to create channel!")
        return await self.account.protocol.channel_create(self.event.guild.id, data)

    async def channel_get(self, channel_id: str) -> Channel:
        """根据 ID 获取频道。返回一个 `Channel` 对象。

        Args:
            channel_id (str): 频道 ID

        Returns:
            Channel: `Channel` 对象
        """
        return await self.account.protocol.channel_get(channel_id)

    def channel_list(self, next_token: str | None = None) -> IterablePageResult[Channel]:
        """获取群组中的全部频道。返回一个 Channel 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Channel]: `Channel` 的分页列表
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to list channel!")
        return self.account.protocol.channel_list(self.event.guild.id, next_token)

    async def channel_update(self, data: Channel) -> None:
        """修改群组频道。

        Args:
            data (Channel): 频道数据

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot use to update channel!")
        return await self.account.protocol.channel_update(self.event.channel.id, data)

    async def channel_delete(self) -> None:
        """删除群组频道。

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot use to delete channel!")
        return await self.account.protocol.channel_delete(self.event.channel.id)

    async def user_channel_create(self, user_id: str | None = None) -> Channel:
        """创建一个私聊频道。返回一个 Channel 对象。

        Args:
            user_id (str | None, optional): 用户 ID，默认为 None（即当前事件的用户）

        Returns:
            Channel: `Channel` 对象
        """
        if not user_id and not self.event.user:
            raise RuntimeError("Event cannot use to create user channel!")
        return await self.account.protocol.user_channel_create(
            user_id or self.event.user.id, self.event.guild.id if self.event.guild else None  # type: ignore
        )

    def guild_member_list(self, next_token: str | None = None) -> IterablePageResult[Member]:
        """获取群组成员列表。返回一个 Member 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Member]: `Member` 的分页列表
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to list member!")
        return self.account.protocol.guild_member_list(self.event.guild.id, next_token)

    async def guild_member_get(self, user_id: str | None = None) -> Member:
        """获取群成员信息。返回一个 `Member` 对象。

        Args:
            user_id (str): 用户 ID

        Returns:
            Member: `Member` 对象
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to get member!")
        if user_id:
            return await self.account.protocol.guild_member_get(self.event.guild.id, user_id)
        if not self.event.user:
            raise RuntimeError("Event cannot use to get member!")
        return await self.account.protocol.guild_member_get(self.event.guild.id, self.event.user.id)

    async def guild_member_kick(self, user_id: str | None = None, permanent: bool = False) -> None:
        """将某个用户踢出群组。

        Args:
            user_id (str): 用户 ID
            permanent (bool, optional): 是否永久踢出 (无法再次加入群组)，默认为 False

        Returns:
            None: 该方法无返回值
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to kick member!")
        if user_id:
            return await self.account.protocol.guild_member_kick(self.event.guild.id, user_id, permanent)
        if not self.event.user:
            raise RuntimeError("Event cannot use to kick member!")
        return await self.account.protocol.guild_member_kick(self.event.guild.id, self.event.user.id, permanent)

    async def guild_member_role_set(self, role_id: str, user_id: str | None = None) -> None:
        """设置群组内用户的角色。

        Args:
            user_id (str): 用户 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to guild member role set!")
        if user_id:
            return await self.account.protocol.guild_member_role_set(self.event.guild.id, user_id, role_id)
        if not self.event.user:
            raise RuntimeError("Event cannot use to guild member role set!")
        return await self.account.protocol.guild_member_role_set(self.event.guild.id, self.event.user.id, role_id)

    async def guild_member_role_unset(self, role_id: str, user_id: str | None = None) -> None:
        """取消群组内用户的角色。

        Args:
            user_id (str): 用户 ID
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to guild member role unset!")
        if user_id:
            return await self.account.protocol.guild_member_role_unset(self.event.guild.id, user_id, role_id)
        if not self.event.user:
            raise RuntimeError("Event cannot use to guild member role unset!")
        return await self.account.protocol.guild_member_role_unset(self.event.guild.id, self.event.user.id, role_id)

    def guild_role_list(self, next_token: str | None = None) -> IterablePageResult[Role]:
        """获取群组角色列表。返回一个 Role 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Role]: `Role` 的分页列表
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to list role!")
        return self.account.protocol.guild_role_list(self.event.guild.id, next_token)

    async def guild_role_create(self, role: Role) -> Role:
        """创建群组角色。返回一个 Role 对象。

        Args:
            role (Role): 角色数据

        Returns:
            Role: `Role` 对象
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to create role!")
        return await self.account.protocol.guild_role_create(self.event.guild.id, role)

    async def guild_role_update(self, role_id: str, role: Role) -> None:
        """修改群组角色。

        Args:
            role_id (str): 角色 ID
            role (Role): 角色数据

        Returns:
            None: 该方法无返回值
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to update role!")
        return await self.account.protocol.guild_role_update(self.event.guild.id, role_id, role)

    async def guild_role_delete(self, role_id: str) -> None:
        """删除群组角色。

        Args:
            role_id (str): 角色 ID

        Returns:
            None: 该方法无返回值
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to delete role!")
        return await self.account.protocol.guild_role_delete(self.event.guild.id, role_id)

    async def reaction_create(self, emoji: str, message_id: str | None = None) -> None:
        """向特定消息添加表态。

        Args:
            message_id (str | None, optional): 消息 ID
            emoji (str): 表态名称

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not message_id and not self.event.message:
            raise RuntimeError("Event cannot create reaction")
        return await self.account.protocol.reaction_create(self.event.channel.id, message_id or self.event.message.id, emoji)  # type: ignore  # noqa: E501

    async def reaction_delete(self, emoji: str, message_id: str | None = None, user_id: str | None = None) -> None:
        """从特定消息删除某个用户添加的特定表态。

        如果没有传入用户 ID 则表示删除自己的表态。

        Args:
            message_id (str | None, optional): 消息 ID
            emoji (str): 表态名称
            user_id (str | None, optional): 用户 ID，默认为 None

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not message_id and not self.event.message:
            raise RuntimeError("Event cannot delete reaction")
        return await self.account.protocol.reaction_delete(self.event.channel.id, message_id or self.event.message.id, emoji, user_id)  # type: ignore  # noqa: E501

    async def reaction_clear(self, emoji: str | None = None, message_id: str | None = None) -> None:
        """从特定消息清除某个特定表态。

        如果没有传入表态名称则表示清除所有表态。

        Args:
            message_id (str | None, optional): 消息 ID
            emoji (str | None, optional): 表态名称，默认为 None

        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not message_id and not self.event.message:
            raise RuntimeError("Event cannot clear reaction")
        return await self.account.protocol.reaction_clear(
            self.event.channel.id,
            message_id or self.event.message.id,  # type: ignore
            emoji,
        )

    def reaction_list(
        self, emoji: str, message_id: str | None = None, next_token: str | None = None
    ) -> IterablePageResult[User]:
        """获取添加特定消息的特定表态的用户列表。返回一个 User 的分页列表。

        Args:
            message_id (str | None, optional): 消息 ID
            emoji (str): 表态名称
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[User]: `User` 的分页列表
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot be replied to!")
        if not message_id and not self.event.message:
            raise RuntimeError("Event cannot list reaction")
        return self.account.protocol.reaction_list(
            self.event.channel.id, message_id or self.event.message.id, emoji, next_token  # type: ignore
        )

    async def request_approve(self, approve: bool, comment: str = ""):
        """处理请求。

        Args:
            approve (bool): 是否通过请求
            comment (str): 备注信息
        Returns:
            None: 该方法无返回值
        """
        if isinstance(self.event, FriendRequestEvent):
            return await self.friend_approve(approve, comment)
        if isinstance(self.event, GuildRequestEvent):
            return await self.guild_approve(approve, comment)
        if isinstance(self.event, GuildMemberRequestEvent):
            return await self.guild_member_approve(approve, comment)
        raise RuntimeError("Event cannot approve request")

    async def friend_approve(self, approve: bool, comment: str = ""):
        """处理好友申请。

        Args:
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """
        if not isinstance(self.event, FriendRequestEvent):
            raise RuntimeError("Event cannot approve friend request")
        return await self.account.protocol.friend_approve(self.event.message.id, approve, comment)

    async def guild_approve(self, approve: bool, comment: str = ""):
        """处理来自群组的邀请。

        Args:
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """
        if not isinstance(self.event, GuildRequestEvent):
            raise RuntimeError("Event cannot approve guild request")
        return await self.account.protocol.guild_approve(self.event.message.id, approve, comment)

    async def guild_member_approve(self, approve: bool, comment: str = ""):
        """处理来自群组的加群请求。

        Args:
            approve (bool): 是否通过请求
            comment (str): 备注信息

        Returns:
            None: 该方法无返回值
        """
        if not isinstance(self.event, GuildMemberRequestEvent):
            raise RuntimeError("Event cannot approve guild member request")
        return await self.account.protocol.guild_member_approve(self.event.message.id, approve, comment)

    async def channel_mute(self, duration: float = 60) -> None:
        """禁言群组频道。

        如果传入的禁言时长为 0 则表示解除禁言。

        Args:
            duration (float, optional): 禁言时长 (秒)，默认为 60 秒
        Returns:
            None: 该方法无返回值
        """
        if not self.event.channel:
            raise RuntimeError("Event cannot use to mute channel!")
        return await self.account.protocol.channel_mute(self.event.channel.id, duration)

    async def guild_get(self, guild_id: str) -> Guild:
        """根据 ID 获取群组。返回一个 `Guild` 对象。

        Args:
            guild_id (str): 群组 ID

        Returns:
            Guild: `Guild` 对象
        """
        return await self.account.protocol.guild_get(guild_id)

    def guild_list(self, next_token: str | None = None) -> IterablePageResult[Guild]:
        """获取当前用户加入的全部群组。返回一个 Guild 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[Guild]: `Guild` 的分页列表
        """
        return self.account.protocol.guild_list(next_token)

    async def guild_member_mute(self, user_id: str, duration: float = 60) -> None:
        """禁言群组成员。

        如果传入的禁言时长为 0 则表示解除禁言。

        Args:
            user_id (str): 用户 ID
            duration (float, optional): 禁言时长 (秒)，默认为 60 秒

        Returns:
            None: 该方法无返回值
        """
        if not self.event.guild:
            raise RuntimeError("Event cannot use to mute guild member!")
        return await self.account.protocol.guild_member_mute(self.event.guild.id, user_id, duration)

    async def login_get(self) -> Login:
        """获取当前登录信息。返回一个 `Login` 对象。

        Returns:
            Login: `Login` 对象
        """
        return await self.account.protocol.login_get()

    async def user_get(self, user_id: str) -> User:
        """获取用户信息。返回一个 `User` 对象。

        Args:
            user_id (str): 用户 ID

        Returns:
            User: `User` 对象
        """
        return await self.account.protocol.user_get(user_id)

    def friend_list(self, next_token: str | None = None) -> IterablePageResult[User]:
        """获取好友列表。返回一个 User 的分页列表。

        Args:
            next_token (str | None, optional): 分页令牌，默认为空

        Returns:
            IterablePageResult[User]: `User` 的分页列表
        """
        return self.account.protocol.friend_list(next_token)

    async def internal(self, action: str, method: str = "POST", **kwargs) -> Any:
        """内部接口调用。

        Args:
            action (str): 内部接口名称
            method (str, optional): 请求方法，默认为 POST
            **kwargs: 参数
        """
        return await self.account.protocol.internal(action, method, **kwargs)

    async def meta_get(self) -> Meta:
        """获取元信息。返回一个 `Meta` 对象。

        Returns:
            Meta: `Meta` 对象
        """
        return await self.account.protocol.meta_get()

    @overload
    async def upload_create(self, *uploads: Upload) -> list[str]: ...
    @overload
    async def upload_create(self, **uploads: Upload) -> dict[str, str]: ...

    async def upload_create(self, *args: Upload, **kwargs: Upload):  # type: ignore
        """上传文件。

        如果要发送的消息中含有图片或其他媒体资源，\
            可以使用此 API 将文件上传至 Satori 服务器并转换为 URL，以便在消息编码中使用。
        """
        return await self.account.protocol.upload_create(*args, **kwargs)

    upload = upload_create

    async def download(self, url: str):
        """访问内部链接。"""
        return await self.account.protocol.download(url)

    async def request_internal(self, url: str, method: str = "GET", **kwargs) -> dict:
        """访问内部链接。"""
        return await self.account.protocol.request_internal(url, method, **kwargs)
