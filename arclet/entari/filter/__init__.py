import asyncio
from collections.abc import Awaitable
from datetime import datetime
from typing import Callable, Final, Optional, Union
from typing_extensions import ParamSpec, TypeAlias

from arclet.letoderea import STOP, Propagator, enter_if
from tarina import get_signature

from . import common, message
from ..message import MessageChain
from ..session import Session
from .common import parse as parse

_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]


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
        params = get_signature(func)
        name = next(iter(params)).name
        func.__annotations__ = {name: Session}
        return enter_if(func)


filter_: Final[_Filter] = _Filter()
F = filter_


class Interval(Propagator):
    def __init__(self, interval: float, limit_prompt: Optional[Union[str, MessageChain]] = None):
        self.success = True
        self.last_time = None
        self.interval = interval
        self.limit_prompt = limit_prompt

    async def before(self, session: Optional[Session] = None):
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
    def __init__(self, count: int, limit_prompt: Optional[Union[str, MessageChain]] = None):
        self.count = count
        self.limit_prompt = limit_prompt
        self.semaphore = asyncio.Semaphore(count)

    async def before(self, session: Optional[Session] = None):
        if not await self.semaphore.acquire():
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self):
        self.semaphore.release()

    def compose(self):
        yield self.before, True, 15
        yield self.after, False, 60
