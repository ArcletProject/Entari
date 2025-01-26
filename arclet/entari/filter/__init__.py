import asyncio
from collections.abc import Awaitable
from datetime import datetime
from typing import Any, Callable, Final, Optional, Union
from typing_extensions import ParamSpec, TypeAlias

from arclet.letoderea import STOP, Depends, Propagator
from arclet.letoderea.typing import Result, TTarget, run_sync
from tarina import is_coroutinefunction

from . import common
from ..message import MessageChain
from ..session import Session
from .common import parse as parse
from .message import direct_message, notice_me, public_message, reply_me, to_me

_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]
P = ParamSpec("P")


def wrapper(func: Callable[P, TTarget]) -> Callable[P, Any]:
    def _wrapper(*args: P.args, **kwargs: P.kwargs):
        async def _(res: Result[bool] = Depends(func(*args, **kwargs))):
            if res.value is False:
                return STOP

        return _

    return _wrapper


class _Filter:
    user = staticmethod(wrapper(common._user))
    guild = staticmethod(wrapper(common._guild))
    channel = staticmethod(wrapper(common._channel))
    self_ = staticmethod(wrapper(common._account))
    platform = staticmethod(wrapper(common._platform))
    direct = staticmethod(direct_message)
    private = staticmethod(direct_message)
    direct_message = staticmethod(direct_message)
    public = staticmethod(public_message)
    public_message = staticmethod(public_message)
    notice_me = staticmethod(notice_me)
    reply_me = staticmethod(reply_me)
    to_me = staticmethod(to_me)

    def __call__(self, func: _SessionFilter):
        _func = run_sync(func) if is_coroutinefunction(func) else func

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

    async def after(self) -> Optional[bool]:
        if self.success:
            self.last_time = datetime.now()
            return True

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
