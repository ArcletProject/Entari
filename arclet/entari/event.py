from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import ClassVar

from arclet.letoderea import Contexts, Param, Provider
from satori import ArgvInteraction, ButtonInteraction, Channel
from satori import Event as SatoriEvent
from satori import EventType, Guild, Login, Member, Quote, Role, User
from satori.client import Account
from satori.model import MessageObject
from tarina import gen_subclass

from .message import MessageChain


@dataclass
class Event:
    type: ClassVar[EventType]
    _origin: SatoriEvent = field(init=False)

    id: int
    timestamp: datetime
    account: Account

    @classmethod
    def parse(cls, account: Account, origin: SatoriEvent):
        fs = fields(cls)
        attrs = {"account": account}
        for fd in fs:
            if not fd.init:
                continue
            if attr := getattr(origin, fd.name, None):
                attrs[fd.name] = attr
        res = cls(**attrs)  # type: ignore
        res._origin = origin
        return res

    async def gather(self, context: Contexts):
        context["$account"] = self.account
        context["$origin_event"] = self._origin

    class AccountProvider(Provider[Account]):
        async def __call__(self, context: Contexts):
            return context["$account"]

    class TimeProvider(Provider[datetime]):
        async def __call__(self, context: Contexts):
            return context["$event"].timestamp

    class OperatorProvider(Provider[User]):
        priority = 10

        def validate(self, param: Param):
            return param.name == "operator" and super().validate(param)

        async def __call__(self, context: Contexts):
            if "operator" in context:
                return context["operator"]
            return context["$origin_event"].operator

    class UserProvider(Provider[User]):
        async def __call__(self, context: Contexts):
            if "user" in context:
                return context["user"]
            return context["$origin_event"].user

    class MessageProvider(Provider[MessageObject]):
        async def __call__(self, context: Contexts):
            if "$message_origin" in context:
                return context["$message_origin"]
            return context["$origin_event"].message

    class ChannelProvider(Provider[Channel]):
        async def __call__(self, context: Contexts):
            if "channel" in context:
                return context["channel"]
            return context["$origin_event"].channel

    class GuildProvider(Provider[Guild]):
        async def __call__(self, context: Contexts):
            if "guild" in context:
                return context["guild"]
            return context["$origin_event"].guild


class NoticeEvent(Event):
    pass


@dataclass
class FriendEvent(NoticeEvent):
    user: User

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["user"] = self.user


class FriendRequestEvent(FriendEvent):
    type = EventType.FRIEND_REQUEST

    message: MessageObject

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["$message_origin"] = self.message


@dataclass
class GuildEvent(NoticeEvent):
    guild: Guild

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["guild"] = self.guild


class GuildAddedEvent(GuildEvent):
    type = EventType.GUILD_ADDED


class GuildRemovedEvent(GuildEvent):
    type = EventType.GUILD_REMOVED


class GuildRequestEvent(GuildEvent):
    type = EventType.GUILD_REQUEST

    message: MessageObject

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["$message_origin"] = self.message


class GuildUpdatedEvent(GuildEvent):
    type = EventType.GUILD_UPDATED


@dataclass
class GuildMemberEvent(GuildEvent):
    user: User
    member: Member | None = None

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["user"] = self.user
        if self.member:
            context["member"] = self.member


class GuildMemberAddedEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_ADDED


class GuildMemberRemovedEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_REMOVED


class GuildMemberRequestEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_REQUEST

    message: MessageObject

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["$message_origin"] = self.message


class GuildMemberUpdatedEvent(GuildMemberEvent):
    type = EventType.GUILD_MEMBER_UPDATED


@dataclass
class GuildRoleEvent(GuildEvent):
    role: Role

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["role"] = self.role

    class RoleProvider(Provider[Role]):
        async def __call__(self, context: Contexts):
            return context.get("role")


class GuildRoleCreatedEvent(GuildRoleEvent):
    type = EventType.GUILD_ROLE_CREATED


class GuildRoleDeletedEvent(GuildRoleEvent):
    type = EventType.GUILD_ROLE_DELETED


class GuildRoleUpdatedEvent(GuildRoleEvent):
    type = EventType.GUILD_ROLE_UPDATED


@dataclass
class LoginEvent(NoticeEvent):
    login: Login

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["login"] = self.login

    class LoginProvider(Provider[Login]):
        async def __call__(self, context: Contexts):
            return context.get("login")


class LoginAddedEvent(LoginEvent):
    type = EventType.LOGIN_ADDED


class LoginRemovedEvent(LoginEvent):
    type = EventType.LOGIN_REMOVED


class LoginUpdatedEvent(LoginEvent):
    type = EventType.LOGIN_UPDATED


class MessageContentProvider(Provider[MessageChain]):
    async def __call__(self, context: Contexts):
        return context["$message_content"]


class QuoteProvider(Provider[Quote]):
    async def __call__(self, context: Contexts):
        return context["$event"].quote


@dataclass
class MessageEvent(Event):
    channel: Channel
    user: User
    message: MessageObject
    content: MessageChain = field(init=False)
    guild: Guild | None = None
    member: Member | None = None
    quote: Quote | None = None

    providers = [MessageContentProvider, QuoteProvider]

    def __post_init__(self):
        self.content = MessageChain(self.message.message)
        if self.content.has(Quote):
            self.quote = self.content.get(Quote, 1)[0]
            self.content = self.content.exclude(Quote)

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["user"] = self.user
        context["channel"] = self.channel
        context["$message_origin"] = self.message
        context["$message_content"] = self.content
        if self.member:
            context["member"] = self.member
        if self.guild:
            context["guild"] = self.guild


class MessageCreatedEvent(MessageEvent):
    type = EventType.MESSAGE_CREATED


class MessageDeletedEvent(MessageEvent):
    type = EventType.MESSAGE_DELETED


class MessageUpdatedEvent(MessageEvent):
    type = EventType.MESSAGE_UPDATED


@dataclass
class ReactionEvent(NoticeEvent):
    channel: Channel
    user: User
    message: MessageObject
    content: MessageChain = field(init=False)
    quote: Quote | None = None
    guild: Guild | None = None
    member: Member | None = None

    providers = [MessageContentProvider, QuoteProvider]

    def __post_init__(self):
        self.content = MessageChain(self.message.message)
        if self.content.has(Quote):
            self.quote = self.content.get(Quote, 1)[0]
            self.content = self.content.exclude(Quote)

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["user"] = self.user
        context["channel"] = self.channel
        context["$message_origin"] = self.message
        context["$message_content"] = self.content
        if self.member:
            context["member"] = self.member
        if self.guild:
            context["guild"] = self.guild


class ReactionAddedEvent(ReactionEvent):
    type = EventType.REACTION_ADDED


class ReactionRemovedEvent(ReactionEvent):
    type = EventType.REACTION_REMOVED


class InternalEvent(Event):
    type = EventType.INTERNAL


class InteractionEvent(NoticeEvent):
    pass


@dataclass
class InteractionButtonEvent(InteractionEvent):
    type = EventType.INTERACTION_BUTTON

    button: ButtonInteraction

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["button"] = self.button

    class ButtonProvider(Provider[ButtonInteraction]):
        async def __call__(self, context: Contexts):
            return context.get("button")


class InteractionCommandEvent(InteractionEvent):
    type = EventType.INTERACTION_COMMAND


@dataclass
class InteractionCommandArgvEvent(InteractionCommandEvent):
    argv: ArgvInteraction

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["argv"] = self.argv

    class ArgvProvider(Provider[ArgvInteraction]):
        async def __call__(self, context: Contexts):
            return context.get("argv")


@dataclass
class InteractionCommandMessageEvent(InteractionCommandEvent):
    channel: Channel
    user: User
    message: MessageObject
    content: MessageChain = field(init=False)
    quote: Quote | None = None
    guild: Guild | None = None
    member: Member | None = None

    providers = [MessageContentProvider, QuoteProvider]

    def __post_init__(self):
        self.content = MessageChain(self.message.message)
        if self.content.has(Quote):
            self.quote = self.content.get(Quote, 1)[0]
            self.content = self.content.exclude(Quote)

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["user"] = self.user
        context["channel"] = self.channel
        context["$message_origin"] = self.message
        context["$message_content"] = self.content
        if self.member:
            context["member"] = self.member
        if self.guild:
            context["guild"] = self.guild


MAPPING = {}

for cls in gen_subclass(Event):
    if hasattr(cls, "type"):
        MAPPING[cls.type.value] = cls


def event_parse(account: Account, event: SatoriEvent):
    try:
        return MAPPING[event.type].parse(account, event)
    except KeyError:
        raise NotImplementedError from None
