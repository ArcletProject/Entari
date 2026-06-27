import asyncio
import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Final, TypeAlias
from typing_extensions import ParamSpec

from arclet.letoderea import STOP, Propagator, enter_if, propagate
from arclet.letoderea.utils import TCallable
from tarina import is_coroutinefunction

from ..config import EntariConfig
from ..message import MessageChain
from ..session import Session
from . import common

_SessionFilter: TypeAlias = Callable[[Session], bool] | Callable[[Session], Awaitable[bool]]


P = ParamSpec("P")


def _check_wrapper(func: Callable[P, _SessionFilter]):
    def wrapper(*args: P.args, **kwargs: P.kwargs):
        return enter_if(func(*args, **kwargs))

    return wrapper


class _Filter:
    user = staticmethod(_check_wrapper(common.user))
    guild = staticmethod(_check_wrapper(common.guild))
    channel = staticmethod(_check_wrapper(common.channel))
    self_ = staticmethod(_check_wrapper(common.account))
    platform = staticmethod(_check_wrapper(common.platform))
    direct = enter_if(common.direct_message)
    private = enter_if(common.direct_message)
    direct_message = enter_if(common.direct_message)
    public = enter_if(common.public_message)
    public_message = enter_if(common.public_message)
    notice_me = enter_if(common.notice_me)
    reply_me = enter_if(common.reply_me)
    to_me = enter_if(common.to_me)

    def __call__(self, func: _SessionFilter):
        sig = inspect.signature(func)
        name = next(iter(sig.parameters.values())).name

        if not is_coroutinefunction(func):

            async def _(*args, _func=func, **kwargs):
                return _func(*args, **kwargs)

            func = _
        func.__signature__ = sig.replace(
            parameters=[
                param.replace(annotation=Session) if param.name == name else param for param in sig.parameters.values()
            ]
        )
        return enter_if(func)


filter_: Final[_Filter] = _Filter()
F = filter_


class interval(Propagator):
    def __init__(self, value: float, limit_prompt: str | MessageChain | None = None, priority: int = 80):
        self.success = True
        self.value = value
        self.priority = priority
        self.limit_prompt = limit_prompt
        self.last_times: dict[str, datetime] = {}

    async def before(self, session: Session | None = None):
        session_id = "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        last_time = self.last_times.get(session_id, None)
        if not last_time:
            return
        self.success = (datetime.now() - last_time).total_seconds() > self.value
        if not self.success:
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self, session: Session | None = None):
        session_id = "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        self.last_times[session_id] = datetime.now()

    def compose(self):
        yield self.before, True, self.priority
        yield self.after, False, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class semaphore(Propagator):
    def __init__(self, count: int, limit_prompt: str | MessageChain | None = None, priority: int = 80):
        self.count = count
        self.limit_prompt = limit_prompt
        self.priority = priority
        self.semaphores: dict[str, asyncio.Semaphore] = {}

    async def before(self, session: Session | None = None):
        session_id = "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        if session_id not in self.semaphores:
            self.semaphores[session_id] = asyncio.Semaphore(self.count)
        if not await self.semaphores[session_id].acquire():
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self, session: Session | None = None):
        session_id = "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        if session_id not in self.semaphores:
            self.semaphores[session_id] = asyncio.Semaphore(self.count)
        self.semaphores[session_id].release()

    def compose(self):
        yield self.before, True, self.priority
        yield self.after, False, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class superusers(Propagator):

    async def check(self, session: Session | None = None):
        if not session:
            return STOP
        config = EntariConfig.instance.basic.superusers
        if session.account.platform not in config:
            return STOP
        if not session.event.user:
            return STOP
        if session.event.user.id not in config[session.account.platform]:
            return STOP

    def compose(self):
        yield self.check, True, 50

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class admins(Propagator):

    async def check(self, session: Session | None = None):
        if not session:
            return STOP
        if session.event.member and session.event.member.roles:
            for role in session.event.member.roles:
                if any(keyword in role.id.lower() for keyword in ("admin", "administrator", "owner")):
                    return
        config = EntariConfig.instance.basic.superusers
        if (
            session.account.platform in config
            and session.event.user
            and session.event.user.id in config[session.account.platform]
        ):
            return
        return STOP

    def compose(self):
        yield self.check, True, 50

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)
