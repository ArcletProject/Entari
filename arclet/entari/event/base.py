from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar, TypeVar, overload

from arclet.letoderea import Contexts, Param, Provider, define
from satori import Event as OriginEvent
from satori.client import Account
from satori.const import EventType
from satori.element import At, Author, Quote, Text, select
from satori.model import (
    ArgvInteraction,
    ButtonInteraction,
    Channel,
    EmojiObject,
    Guild,
    Login,
    Member,
    MessageObject,
    Role,
    User,
)
from tarina import gen_subclass

from ..const import (
    ITEM_ACCOUNT,
    ITEM_GUILD,
    ITEM_MESSAGE_CONTENT,
    ITEM_MESSAGE_ORIGIN,
    ITEM_MESSAGE_REPLY,
    ITEM_ORIGIN_EVENT,
)
from ..message import MessageChain, Reply

T = TypeVar("T")
D = TypeVar("D")


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


class Attr:
    def __init__(self, key: str | None = None, cls: Callable[..., T] | None = None, internal: bool = False):
        self.key = key or ""
        self.cls_ = cls
        self.internal = internal

    def __set_name__(self, owner: type["SatoriEvent"], name: str):
        self.key = self.key or name
        if name not in ("id", "timestamp"):
            owner._attrs.add(name)

    def __get__(self, instance: "SatoriEvent", owner: type["SatoriEvent"]):
        if self.internal and instance._origin._data:
            val = instance._origin._data.get(self.key)
        else:
            val = getattr(instance._origin, self.key, None)
        if self.cls_ and val is not None:
            return self.cls_(val)
        return val

    def __set__(self, instance: "SatoriEvent", value):
        raise AttributeError("can't set attribute")


@overload
def attr(*, internal: bool = False) -> Any: ...


@overload
def attr(key: str, /, *, internal: bool = False) -> Any: ...


@overload
def attr(cls: Callable[..., T], /, *, internal: bool = False) -> T: ...


@overload
def attr(key: str, cls: Callable[..., T], /, *, internal: bool = False) -> T: ...


def attr(*args, internal: bool = False) -> Any:
    if not args:
        return Attr(internal=internal)
    key = args[0] if isinstance(args[0], str) else None
    cls = args[1] if len(args) == 2 else (args[0] if not isinstance(args[0], str) else None)
    return Attr(key, cls, internal)


class SatoriEvent:
    type: ClassVar[str]
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
    referrer: dict | None = attr()
    emoji: EmojiObject | None = attr()

    def __init_subclass__(cls, **kwargs):
        cls._attrs = set()

    def __init__(self, account: Account, origin: OriginEvent):
        self.account = account
        self._origin = origin

    async def gather(self, context: Contexts):
        context[ITEM_ACCOUNT] = self.account
        context[ITEM_ORIGIN_EVENT] = self._origin

        for name in self.__class__._attrs:
            value = getattr(self, name)
            if value is not None:
                context[ITEM_MESSAGE_ORIGIN if name == "message" else f"${name}"] = value

    class TimeProvider(Provider[datetime]):
        def validate(self, param: Param):
            return super().validate(param) and param.name == "event_time"

        async def __call__(self, context: Contexts):
            if "$event" in context:
                return context["$event"].timestamp

    def __repr__(self):
        return f"<{self.__class__.__name__.removesuffix('Event')}{self._origin!r}>"


class NoticeEvent(SatoriEvent):
    pass


class FriendEvent(NoticeEvent):
    user: User = attr()


class FriendAddedEvent(FriendEvent):
    type = EventType.FRIEND_ADDED


class FriendRemovedEvent(FriendEvent):
    type = EventType.FRIEND_REMOVED


class FriendRequestEvent(FriendEvent):
    type = EventType.FRIEND_REQUEST

    message: MessageObject = attr()


class GuildEvent(NoticeEvent):
    guild: Guild = attr()

    async def gather(self, context: Contexts):
        await super().gather(context)
        context[ITEM_GUILD] = self.guild


class GuildAddedEvent(GuildEvent):
    type = EventType.GUILD_ADDED


class GuildRemovedEvent(GuildEvent):
    type = EventType.GUILD_REMOVED


class GuildRequestEvent(GuildEvent):
    type = EventType.GUILD_REQUEST

    message: MessageObject = attr()


class GuildUpdatedEvent(GuildEvent):
    type = EventType.GUILD_UPDATED


class ChannelEvent(GuildEvent):
    channel: Channel = attr()


class ChannelAddedEvent(ChannelEvent):
    type = EventType.CHANNEL_ADDED


class ChannelUpdatedEvent(ChannelEvent):
    type = EventType.CHANNEL_UPDATED


class ChannelRemovedEvent(ChannelEvent):
    type = EventType.CHANNEL_REMOVED


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


class GuildEmojiEvent(GuildEvent):
    emoji: EmojiObject = attr()


class GuildEmojiAddedEvent(GuildEmojiEvent):
    type = EventType.GUILD_EMOJI_ADDED


class GuildEmojiRemovedEvent(GuildEmojiEvent):
    type = EventType.GUILD_EMOJI_REMOVED


class GuildEmojiUpdatedEvent(GuildEmojiEvent):
    type = EventType.GUILD_EMOJI_UPDATED


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


class ReplyProvider(Provider[Reply]):
    async def __call__(self, context: Contexts):
        return context.get(ITEM_MESSAGE_REPLY)


class MessageEvent(SatoriEvent):
    channel: Channel = attr()
    user: User = attr()
    message: MessageObject = attr()

    content: MessageChain
    quote: Quote | None = None

    providers = [ReplyProvider]

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
            if self.quote.children:
                mo = MessageObject.from_elements(self.quote.id, self.quote.children)
            else:
                mo = await self.account.protocol.message_get(self.channel.id, self.quote.id)
            reply = context[ITEM_MESSAGE_REPLY] = Reply(self.quote, mo)
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
        context[ITEM_MESSAGE_CONTENT] = self.content


class MessageCreatedEvent(MessageEvent):
    type = EventType.MESSAGE_CREATED


class MessageDeletedEvent(MessageEvent):
    type = EventType.MESSAGE_DELETED


class MessageUpdatedEvent(MessageEvent):
    type = EventType.MESSAGE_UPDATED


class ReactionEvent(NoticeEvent, MessageEvent):
    emoji: EmojiObject = attr()


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
            return context.get("$button")


class InteractionCommandEvent(InteractionEvent):
    type = EventType.INTERACTION_COMMAND


class InteractionCommandArgvEvent(InteractionCommandEvent):
    argv: ArgvInteraction = attr()

    class ArgvProvider(Provider[ArgvInteraction]):
        async def __call__(self, context: Contexts):
            return context.get("$argv")


class InteractionCommandMessageEvent(InteractionCommandEvent, MessageEvent):
    pass


MAPPING: dict[str, type[SatoriEvent]] = {}

for cls in gen_subclass(SatoriEvent):
    if hasattr(cls, "type"):
        typ = cls.type.value if isinstance(cls.type, EventType) else cls.type
        MAPPING[typ] = cls
        define(cls, name=typ)


INTERNAL_ADDITIONAL_HANDLERS: list[Callable[[str, str, dict[str, Any]], type[SatoriEvent] | None]] = []


def event_parse(account: Account, event: OriginEvent):
    constructor_cls = MAPPING.get(event.type)
    if (constructor_cls is None or event.type == EventType.INTERNAL) and event._type and event._data:
        found = next((h(event.type, event._type, event._data) for h in INTERNAL_ADDITIONAL_HANDLERS), None)
        if found is not None:
            constructor_cls = found
            define(constructor_cls, name=constructor_cls.type)
    if constructor_cls is None:
        raise NotImplementedError(f"Unsupported event type: {event.type}")
    return constructor_cls(account, event)


def register_internal_event(func: Callable[[str, str, dict[str, Any]], type[SatoriEvent] | None]):
    INTERNAL_ADDITIONAL_HANDLERS.append(func)
