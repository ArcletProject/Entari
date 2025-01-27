import asyncio
from collections.abc import Awaitable
from datetime import datetime
from typing import Callable, Final, Optional, Union
from typing_extensions import TypeAlias

from arclet.letoderea import STOP, Propagator
from arclet.letoderea.typing import run_sync
from tarina import is_coroutinefunction

from . import common, message
from ..message import MessageChain
from ..session import Session
from .common import parse as parse

_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]


class _Filter:
    user = staticmethod(common.user)
    guild = staticmethod(common.guild)
    channel = staticmethod(common.channel)
    self_ = staticmethod(common.account)
    platform = staticmethod(common.platform)
    direct = staticmethod(message.direct_message)
    private = staticmethod(message.direct_message)
    direct_message = staticmethod(message.direct_message)
    public = staticmethod(message.public_message)
    public_message = staticmethod(message.public_message)
    notice_me = staticmethod(message.notice_me)
    reply_me = staticmethod(message.reply_me)
    to_me = staticmethod(message.to_me)

    def __call__(self, func: _SessionFilter):
        _func = func if is_coroutinefunction(func) else run_sync(func)

        async def _(session: Session):
            if not await _func(session):  # type: ignore
                return STOP

        return _


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
        if self.success:
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
