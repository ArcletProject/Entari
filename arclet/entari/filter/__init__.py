import asyncio
from collections.abc import Awaitable
from datetime import datetime
from functools import wraps
from typing import Callable, Final, Optional, Union
from typing_extensions import ParamSpec, Self, TypeAlias

from arclet.letoderea import STOP, Propagator, propagate
from arclet.letoderea.typing import TCallable, run_sync
from tarina import is_coroutinefunction

from . import common, message
from ..message import MessageChain
from ..session import Session
from .common import parse as parse

_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]


class _Check(Propagator):
    def __init__(self, func: Union[Callable[..., bool], Callable[..., Awaitable[bool]]]):
        self.predicates = [func]

    def append(self, predicate: Union["_Check", Callable[..., bool], Callable[..., Awaitable[bool]]]) -> Self:
        if isinstance(predicate, _Check):
            self.predicates.extend(predicate.predicates)
        else:
            self.predicates.append(predicate)
        return self

    __and__ = append
    __or__ = append

    def checkers(self):
        for predicate in self.predicates:
            func = predicate if is_coroutinefunction(predicate) else run_sync(predicate)

            @wraps(predicate)
            async def _(*args, _func=func, **kwargs):
                if await _func(*args, **kwargs) is False:
                    return STOP

            yield _

    def compose(self):
        for checker in self.checkers():
            yield checker, True, 0

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


P = ParamSpec("P")


def _check_wrapper(func: Callable[P, _SessionFilter]) -> Callable[P, _Check]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> _Check:
        return _Check(func(*args, **kwargs))

    return wrapper


class _Filter:
    user = staticmethod(_check_wrapper(common.user))
    guild = staticmethod(_check_wrapper(common.guild))
    channel = staticmethod(_check_wrapper(common.channel))
    self_ = staticmethod(_check_wrapper(common.account))
    platform = staticmethod(_check_wrapper(common.platform))
    direct = _Check(message.direct_message)
    private = _Check(message.direct_message)
    direct_message = _Check(message.direct_message)
    public = _Check(message.public_message)
    public_message = _Check(message.public_message)
    notice_me = _Check(message.notice_me)
    reply_me = _Check(message.reply_me)
    to_me = _Check(message.to_me)

    def __call__(self, func: _SessionFilter):
        return _Check(func)


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
