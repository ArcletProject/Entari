from collections.abc import Awaitable
from typing import Callable, Optional, Union
from typing_extensions import Self, TypeAlias

from arclet.letoderea import BaseAuxiliary, Interface
from arclet.letoderea import bind as _bind
from arclet.letoderea.auxiliary import sort_auxiliaries
from arclet.letoderea.typing import run_sync
from satori import Channel, Guild, User
from satori.client import Account
from tarina import is_async

from ..event.base import SatoriEvent
from ..session import Session
from .message import DirectMessageJudger, NoticeMeJudger, PublicMessageJudger, ReplyMeJudger, ToMeJudger
from .op import ExcludeFilter, IntersectFilter, UnionFilter


class PlatformFilter(BaseAuxiliary):
    def __init__(self, *platforms: str):
        self.platforms = set(platforms)

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (account := await interface.query(Account, "account", force_return=True)):
            return False
        return account.platform in self.platforms

    @property
    def id(self) -> str:
        return "entari.filter/platform"


class SelfFilter(BaseAuxiliary):
    def __init__(self, *self_ids: str):
        self.self_ids = set(self_ids)

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (account := await interface.query(Account, "account", force_return=True)):
            return False
        return account.self_id in self.self_ids

    @property
    def id(self) -> str:
        return "entari.filter/self"

    @property
    def before(self) -> set[str]:
        return {"entari.filter/platform"}


class GuildFilter(BaseAuxiliary):
    def __init__(self, *guild_ids: str):
        self.guild_ids = set(guild_ids)

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (guild := await interface.query(Guild, "guild", force_return=True)):
            return False
        return guild.id in self.guild_ids if self.guild_ids else True

    @property
    def id(self) -> str:
        return "entari.filter/guild"

    @property
    def before(self) -> set[str]:
        return {"entari.filter/platform", "entari.filter/self"}


class ChannelFilter(BaseAuxiliary):
    def __init__(self, *channel_ids: str):
        self.channel_ids = set(channel_ids)

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.id in self.channel_ids if self.channel_ids else True

    @property
    def id(self) -> str:
        return "entari.filter/channel"

    @property
    def before(self) -> set[str]:
        return {"entari.filter/platform", "entari.filter/self", "entari.filter/guild"}


class UserFilter(BaseAuxiliary):
    def __init__(self, *user_ids: str):
        self.user_ids = set(user_ids)

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (user := await interface.query(User, "user", force_return=True)):
            return False
        return user.id in self.user_ids if self.user_ids else True

    @property
    def id(self) -> str:
        return "entari.filter/user"

    @property
    def before(self) -> set[str]:
        return {"entari.filter/platform", "entari.filter/self"}


_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]
_keys = {
    "user",
    "guild",
    "channel",
    "self",
    "platform",
    "direct",
    "private",
    "public",
    "reply_me",
    "notice_me",
    "to_me",
}

PATTERNS: TypeAlias = dict[str, Union[list[str], bool, "PATTERNS"]]


class Filter(BaseAuxiliary):
    def __init__(self, callback: Optional[_SessionFilter] = None):
        self.steps = []
        if callback:
            if is_async(callback):
                self.callback = callback
            else:
                self.callback = run_sync(callback)
        else:
            self.callback = None

    def __repr__(self):
        return f"{self.__class__.__name__}({self.steps})"

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not isinstance(interface.event, SatoriEvent):  # we only care about event from satori
            return True
        for step in sort_auxiliaries(self.steps):
            if not await step.on_prepare(interface):
                return False
        if self.callback:
            session = await interface.query(Session, "session", force_return=True)
            if not session:
                return False
            if not await self.callback(session):  # type: ignore
                return False
        return True

    @property
    def id(self) -> str:
        return "entari.filter"

    def platform(self, *platforms: str) -> Self:
        self.steps.append(PlatformFilter(*platforms))
        return self

    def self(self, *self_ids: str) -> Self:
        self.steps.append(SelfFilter(*self_ids))
        return self

    def guild(self, *guild_ids: str) -> Self:
        self.steps.append(GuildFilter(*guild_ids))
        return self

    def channel(self, *channel_ids: str) -> Self:
        self.steps.append(ChannelFilter(*channel_ids))
        return self

    def user(self, *user_ids: str) -> Self:
        self.steps.append(UserFilter(*user_ids))
        return self

    def direct(self) -> Self:
        self.steps.append(DirectMessageJudger())
        return self

    private = direct

    def public(self) -> Self:
        self.steps.append(PublicMessageJudger())
        return self

    def reply_me(self) -> Self:
        self.steps.append(ReplyMeJudger())
        return self

    def notice_me(self) -> Self:
        self.steps.append(NoticeMeJudger())
        return self

    def to_me(self) -> Self:
        self.steps.append(ToMeJudger())
        return self

    def bind(self, func):
        return _bind(self)(func)

    def and_(self, other: Union["Filter", _SessionFilter]) -> "Filter":
        new = Filter()
        _other = other if isinstance(other, Filter) else Filter(callback=other)
        new.steps.append(IntersectFilter(self, _other))
        return new

    intersect = and_

    def or_(self, other: Union["Filter", _SessionFilter]) -> "Filter":
        new = Filter()
        _other = other if isinstance(other, Filter) else Filter(callback=other)
        new.steps.append(UnionFilter(self, _other))
        return new

    union = or_

    def not_(self, other: Union["Filter", _SessionFilter]) -> "Filter":
        new = Filter()
        _other = other if isinstance(other, Filter) else Filter(callback=other)
        new.steps.append(ExcludeFilter(self, _other))
        return new

    exclude = not_

    @classmethod
    def parse(cls, patterns: PATTERNS) -> Self:
        fter = cls()
        for key, value in patterns.items():
            if key in _keys:
                if isinstance(value, list):
                    getattr(fter, key)(*value)
                elif isinstance(value, bool) and value:
                    getattr(fter, key)()
            elif key in ("$and", "$or", "$not", "$intersect", "$union", "$exclude"):
                op = key[1:]
                if op in ("and", "or", "not"):
                    op += "_"
                if not isinstance(value, dict):
                    raise ValueError(f"Expect a dict for operator {key}")
                fter = getattr(fter, op)(cls.parse(value))
            else:
                raise ValueError(f"Unknown key: {key}")
        return fter
