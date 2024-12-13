from collections.abc import Awaitable
from typing import Callable, Optional, Union
from typing_extensions import Self, TypeAlias

from arclet.letoderea import Interface, JudgeAuxiliary, Scope
from arclet.letoderea import bind as _bind
from arclet.letoderea.typing import run_sync
from satori import Channel, Guild, User
from satori.client import Account
from tarina import is_async

from ..session import Session
from .message import DirectMessageJudger, NoticeMeJudger, PublicMessageJudger, ReplyMeJudger, ToMeJudger
from .op import ExcludeFilter, IntersectFilter, UnionFilter


class UserFilter(JudgeAuxiliary):
    def __init__(self, *user_ids: str, priority: int = 10):
        self.user_ids = set(user_ids)
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (user := await interface.query(User, "user", force_return=True)):
            return False
        return user.id in self.user_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/user"


class GuildFilter(JudgeAuxiliary):
    def __init__(self, *guild_ids: str, priority: int = 10):
        self.guild_ids = set(guild_ids)
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (guild := await interface.query(Guild, "guild", force_return=True)):
            return False
        return guild.id in self.guild_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/guild"


class ChannelFilter(JudgeAuxiliary):
    def __init__(self, *channel_ids: str, priority: int = 10):
        self.channel_ids = set(channel_ids)
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.id in self.channel_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/channel"


class SelfFilter(JudgeAuxiliary):
    def __init__(self, *self_ids: str, priority: int = 20):
        self.self_ids = set(self_ids)
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (account := await interface.query(Account, "account", force_return=True)):
            return False
        return account.self_id in self.self_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/self"


class PlatformFilter(JudgeAuxiliary):
    def __init__(self, *platforms: str, priority: int = 10):
        self.platforms = set(platforms)
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (account := await interface.query(Account, "account", force_return=True)):
            return False
        return account.platform in self.platforms

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/platform"


_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]


class Filter(JudgeAuxiliary):
    def __init__(self, callback: Optional[_SessionFilter] = None, priority: int = 10):
        super().__init__(priority=priority)
        self.steps = []
        if callback:
            if is_async(callback):
                self.callback = callback
            else:
                self.callback = run_sync(callback)
        else:
            self.callback = None

    async def __call__(self, scope: Scope, interface: Interface):
        for step in sorted(self.steps, key=lambda x: x.priority):
            if not await step(scope, interface):
                return False
        if self.callback:
            session = await interface.query(Session, "session", force_return=True)
            if not session:
                return False
            if not await self.callback(session):  # type: ignore
                return False
        return True

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter"

    def user(self, *user_ids: str) -> Self:
        self.steps.append(UserFilter(*user_ids, priority=6))
        return self

    def guild(self, *guild_ids: str) -> Self:
        self.steps.append(GuildFilter(*guild_ids, priority=4))
        return self

    def channel(self, *channel_ids: str) -> Self:
        self.steps.append(ChannelFilter(*channel_ids, priority=5))
        return self

    def self(self, *self_ids: str) -> Self:
        self.steps.append(SelfFilter(*self_ids, priority=3))
        return self

    def platform(self, *platforms: str) -> Self:
        self.steps.append(PlatformFilter(*platforms, priority=2))
        return self

    @property
    def direct(self) -> Self:
        self.steps.append(DirectMessageJudger(priority=8))
        return self

    private = direct

    @property
    def public(self) -> Self:
        self.steps.append(PublicMessageJudger(priority=8))
        return self

    @property
    def reply_me(self) -> Self:
        self.steps.append(ReplyMeJudger(priority=9))
        return self

    @property
    def notice_me(self) -> Self:
        self.steps.append(NoticeMeJudger(priority=10))
        return self

    @property
    def to_me(self) -> Self:
        self.steps.append(ToMeJudger(priority=11))
        return self

    def bind(self, func):
        return _bind(self)(func)

    def and_(self, other: Union["Filter", _SessionFilter]) -> "Filter":
        new = Filter(priority=self.priority)
        _other = other if isinstance(other, Filter) else Filter(callback=other)
        new.steps.append(IntersectFilter(self, _other, priority=1))
        return new

    intersect = and_

    def or_(self, other: Union["Filter", _SessionFilter]) -> "Filter":
        new = Filter(priority=self.priority)
        _other = other if isinstance(other, Filter) else Filter(callback=other)
        new.steps.append(UnionFilter(self, _other, priority=1))
        return new

    union = or_

    def not_(self, other: Union["Filter", _SessionFilter]) -> "Filter":
        new = Filter(priority=self.priority)
        _other = other if isinstance(other, Filter) else Filter(callback=other)
        new.steps.append(ExcludeFilter(self, _other, priority=1))
        return new

    exclude = not_
