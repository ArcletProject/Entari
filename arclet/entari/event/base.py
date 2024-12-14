from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Generic, TypeVar

from arclet.letoderea import Contexts, Param, Provider
from satori import ArgvInteraction, ButtonInteraction, Channel
from satori import Event as OriginEvent
from satori import EventType, Guild, Member, Role, User
from satori.client import Account
from satori.element import At, Author, Quote, Text, select
from satori.model import Login, MessageObject
from tarina import gen_subclass

from ..message import MessageChain

T = TypeVar("T")
D = TypeVar("D")


@dataclass
class Reply:
    quote: Quote
    origin: MessageObject


def _is_reply_me(reply: Reply, account: Account):
    if reply.origin.user:
        return reply.origin.user.id == account.self_id
    if authors := select(reply.quote, Author):
        return any(author.id == account.self_id for author in authors)
    return False


def _is_notice_me(message: MessageChain, account: Account):
    if message and isinstance(message[0], At):
        at: At = message[0]  # type: ignore
        if at.id and at.id == account.self_id:
            return True
    return False


def _remove_notice_me(message: MessageChain, account: Account):
    message = message.copy()
    message.pop(0)
    if _is_notice_me(message, account):
        message.pop(0)
    if message and isinstance(message[0], Text):
        text = message[0].text.lstrip()  # type: ignore
        if not text:
            message.pop(0)
        else:
            message[0] = Text(text)
    return message


class Attr(Generic[T]):
    def __init__(self, key: str | None = None):
        self.key = key

    def __set_name__(self, owner: type[SatoriEvent], name: str):
        self.key = self.key or name
        if name not in ("id", "timestamp"):
            owner._attrs.add(name)

    def __get__(self, instance: SatoriEvent, owner: type[SatoriEvent]) -> T:
        return getattr(instance._origin, self.key, None)  # type: ignore

    def __set__(self, instance: SatoriEvent, value):
        raise AttributeError("can't set attribute")


def attr(key: str | None = None) -> Any:
    return Attr(key)


class SatoriEvent:
    type: ClassVar[EventType]
    _attrs: ClassVar[set[str]] = set()
    _origin: OriginEvent
    account: Account

    sn: int = attr()
    timestamp: datetime = attr()
    login: Login = attr()
    argv: ArgvInteraction | None = attr()
    button: ButtonInteraction | None = attr()
    channel: Channel | None = attr()
    guild: Guild | None = attr()
    member: Member | None = attr()
    message: MessageObject | None = attr()
    operator: User | None = attr()
    role: Role | None = attr()
    user: User | None = attr()

    def __init__(self, account: Account, origin: OriginEvent):
        self.account = account
        self._origin = origin

    async def gather(self, context: Contexts):
        context["account"] = self.account
        context["$origin_event"] = self._origin

        for name in self.__class__._attrs:
            value = getattr(self, name)
            if value is not None:
                context["$message_origin" if name == "message" else name] = value

    class TimeProvider(Provider[datetime]):
        async def __call__(self, context: Contexts):
            if "$event" in context:
                return context["$event"].timestamp

    class OperatorProvider(Provider[User]):
        priority = 10

        def validate(self, param: Param):
            return param.name == "operator" and super().validate(param)

        async def __call__(self, context: Contexts):
            if "operator" in context:
                return context["operator"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].operator

    class UserProvider(Provider[User]):
        async def __call__(self, context: Contexts):
            if "user" in context:
                return context["user"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].user

    class MessageProvider(Provider[MessageObject]):
        async def __call__(self, context: Contexts):
            if "$message_origin" in context:
                return context["$message_origin"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].message

    class ChannelProvider(Provider[Channel]):
        async def __call__(self, context: Contexts):
            if "channel" in context:
                return context["channel"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].channel

    class GuildProvider(Provider[Guild]):
        async def __call__(self, context: Contexts):
            if "guild" in context:
                return context["guild"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].guild

    class MemberProvider(Provider[Member]):
        async def __call__(self, context: Contexts):
            if "member" in context:
                return context["member"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].member

    class RoleProvider(Provider[Role]):
        async def __call__(self, context: Contexts):
            if "role" in context:
                return context["role"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].role

    class LoginProvider(Provider[Login]):
        async def __call__(self, context: Contexts):
            if "login" in context:
                return context["login"]
            if "$origin_event" not in context:
                return
            return context["$origin_event"].login

    def __repr__(self):
        return f"<{self.__class__.__name__[:-5]}{self._origin!r}>"


class NoticeEvent(SatoriEvent):
    pass


class FriendEvent(NoticeEvent):
    user: User = attr()


class FriendRequestEvent(FriendEvent):
    type = EventType.FRIEND_REQUEST

    message: MessageObject = attr()


class GuildEvent(NoticeEvent):
    guild: Guild = attr()

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["guild"] = self.guild


class GuildAddedEvent(GuildEvent):
    type = EventType.GUILD_ADDED


class GuildRemovedEvent(GuildEvent):
    type = EventType.GUILD_REMOVED


class GuildRequestEvent(GuildEvent):
    type = EventType.GUILD_REQUEST

    message: MessageObject = attr()


class GuildUpdatedEvent(GuildEvent):
    type = EventType.GUILD_UPDATED


class GuildMemberEvent(GuildEvent):
    user: User = attr()


class GuildMemberAddedEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_ADDED


class GuildMemberRemovedEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_REMOVED


class GuildMemberRequestEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_REQUEST

    message: MessageObject = attr()


class GuildMemberUpdatedEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_UPDATED


class GuildRoleEvent(GuildEvent):
    role: Role = attr()


class GuildRoleCreatedEvent(GuildRoleEvent):
    type = EventType.GUILD_ROLE_CREATED


class GuildRoleDeletedEvent(GuildRoleEvent):
    type = EventType.GUILD_ROLE_DELETED


class GuildRoleUpdatedEvent(GuildRoleEvent):
    type = EventType.GUILD_ROLE_UPDATED


class LoginEvent(NoticeEvent):
    pass


class LoginAddedEvent(LoginEvent):
    type = EventType.LOGIN_ADDED


class LoginRemovedEvent(LoginEvent):
    type = EventType.LOGIN_REMOVED


class LoginUpdatedEvent(LoginEvent):
    type = EventType.LOGIN_UPDATED


class MessageContentProvider(Provider[MessageChain]):
    priority = 30

    async def __call__(self, context: Contexts):
        return context.get("$message_content")


class ReplyProvider(Provider[Reply]):
    async def __call__(self, context: Contexts):
        return context.get("$message_reply")


class MessageEvent(SatoriEvent):
    channel: Channel = attr()
    user: User = attr()
    message: MessageObject = attr()

    content: MessageChain
    quote: Quote | None = None

    providers = [MessageContentProvider, ReplyProvider]

    def __init__(self, account: Account, origin: OriginEvent):
        super().__init__(account, origin)
        self.content = MessageChain(self.message.message)
        if self.content.has(Quote):
            self.quote = self.content.get(Quote, 1)[0]
            self.content = self.content.exclude(Quote)

    async def gather(self, context: Contexts):
        await super().gather(context)
        reply = None
        if self.quote and self.quote.id:
            mo = await self.account.protocol.message_get(self.channel.id, self.quote.id)
            reply = context["$message_reply"] = Reply(self.quote, mo)
        if not reply:
            is_reply_me = False
        else:
            is_reply_me = _is_reply_me(reply, self.account)
        context["is_reply_me"] = is_reply_me
        if is_reply_me and self.content and isinstance(self.content[0], Text):
            text = self.content[0].text.lstrip()
            if not text:
                self.content.pop(0)
            else:
                self.content[0] = Text(text)
        is_notice_me = context["is_notice_me"] = _is_notice_me(self.content, self.account)
        if is_notice_me:
            self.content = _remove_notice_me(self.content, self.account)
        context["$message_content"] = self.content


class MessageCreatedEvent(MessageEvent):
    type = EventType.MESSAGE_CREATED


class MessageDeletedEvent(MessageEvent):
    type = EventType.MESSAGE_DELETED


class MessageUpdatedEvent(MessageEvent):
    type = EventType.MESSAGE_UPDATED


class ReactionEvent(NoticeEvent, MessageEvent):
    pass


class ReactionAddedEvent(ReactionEvent):
    type = EventType.REACTION_ADDED


class ReactionRemovedEvent(ReactionEvent):
    type = EventType.REACTION_REMOVED


class InternalEvent(SatoriEvent):
    type = EventType.INTERNAL


class InteractionEvent(NoticeEvent):
    pass


class InteractionButtonEvent(InteractionEvent):
    type = EventType.INTERACTION_BUTTON

    button: ButtonInteraction = attr()

    class ButtonProvider(Provider[ButtonInteraction]):
        async def __call__(self, context: Contexts):
            return context.get("button")


class InteractionCommandEvent(InteractionEvent):
    type = EventType.INTERACTION_COMMAND


class InteractionCommandArgvEvent(InteractionCommandEvent):
    argv: ArgvInteraction = attr()

    class ArgvProvider(Provider[ArgvInteraction]):
        async def __call__(self, context: Contexts):
            return context.get("argv")


class InteractionCommandMessageEvent(InteractionCommandEvent, MessageEvent):
    pass


MAPPING: dict[str, type[SatoriEvent]] = {}

for cls in gen_subclass(SatoriEvent):
    if hasattr(cls, "type"):
        MAPPING[cls.type.value] = cls


def event_parse(account: Account, event: OriginEvent):
    try:
        return MAPPING[event.type](account, event)
    except KeyError:
        raise NotImplementedError from None
