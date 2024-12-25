import asyncio
from datetime import datetime
from typing import Optional, Union

from arclet.letoderea import BaseAuxiliary, Interface

from ..message import MessageChain
from ..session import Session
from .common import Filter as Filter


class Interval(BaseAuxiliary):
    def __init__(self, interval: float, limit_prompt: Optional[Union[str, MessageChain]] = None):
        self.success = True
        self.last_time = None
        self.interval = interval
        self.limit_prompt = limit_prompt

    @property
    def id(self):
        return "entari.filter/interval"

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not self.last_time:
            return True
        self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
        if not self.success:
            session = await interface.query(Session, "session", force_return=True)
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
        return self.success

    async def on_cleanup(self, interface: Interface) -> Optional[bool]:
        if self.success:
            self.last_time = datetime.now()
            return True


class Semaphore(BaseAuxiliary):
    def __init__(self, count: int, limit_prompt: Optional[Union[str, MessageChain]] = None):
        self.count = count
        self.limit_prompt = limit_prompt
        self.semaphore = asyncio.Semaphore(count)

    @property
    def id(self):
        return "entari.filter/access"

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not await self.semaphore.acquire():
            session = await interface.query(Session, "session", force_return=True)
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return False
        return True

    async def on_cleanup(self, interface: Interface) -> Optional[bool]:
        self.semaphore.release()
        return True
