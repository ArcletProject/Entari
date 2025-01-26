import asyncio
from datetime import datetime
from typing import Optional, Union

from arclet.letoderea import STOP, Propagator

from ..message import MessageChain
from ..session import Session
from .common import filter_ as filter_
from .common import parse as parse
from .message import direct_message
from .message import notice_me as notice_me
from .message import public_message
from .message import reply_me as reply_me
from .message import to_me as to_me

s = filter_
direct = direct_message
public = public_message
private = direct_message


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
