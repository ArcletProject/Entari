import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
import inspect
from typing import Final, TypeAlias
from typing_extensions import ParamSpec

from arclet.letoderea import STOP, Propagator, enter_if
from tarina import is_coroutinefunction

from . import common, message
from ..message import MessageChain
from ..session import Session
from .common import parse as parse

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
    direct = enter_if(message.direct_message)
    private = enter_if(message.direct_message)
    direct_message = enter_if(message.direct_message)
    public = enter_if(message.public_message)
    public_message = enter_if(message.public_message)
    notice_me = enter_if(message.notice_me)
    reply_me = enter_if(message.reply_me)
    to_me = enter_if(message.to_me)

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


class Interval(Propagator):
    def __init__(self, interval: float, limit_prompt: str | MessageChain | None = None):
        self.success = True
        self.last_time = None
        self.interval = interval
        self.limit_prompt = limit_prompt

    async def before(self, session: Session | None = None):
        if not self.last_time:
            return
        self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
        if not self.success:
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self):
        self.last_time = datetime.now()

    def compose(self):
        yield self.before, True, 15
        yield self.after, False, 60


class Semaphore(Propagator):
    def __init__(self, count: int, limit_prompt: str | MessageChain | None = None):
        self.count = count
        self.limit_prompt = limit_prompt
        self.semaphore = asyncio.Semaphore(count)

    async def before(self, session: Session | None = None):
        if not await self.semaphore.acquire():
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self):
        self.semaphore.release()

    def compose(self):
        yield self.before, True, 15
        yield self.after, False, 60
