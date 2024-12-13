import asyncio
from datetime import datetime
from typing import Optional, Union

from arclet.letoderea import Interface, JudgeAuxiliary, Scope

from ..message import MessageChain
from ..session import Session
from .common import Filter as Filter


class Interval(JudgeAuxiliary):
    def __init__(self, interval: float, limit_prompt: Optional[Union[str, MessageChain]] = None):
        self.success = True
        self.last_time = None
        self.interval = interval
        self.limit_prompt = limit_prompt
        super().__init__(priority=20)

    @property
    def id(self):
        return "entari.filter/interval"

    @property
    def scopes(self):
        return {Scope.prepare, Scope.cleanup}

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if scope == Scope.prepare:
            if not self.last_time:
                return True
            # if self.condition:
            #     if not await self.condition(scope, interface):
            #         self.success = False
            #         return False
            self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
            if not self.success:
                session = await interface.query(Session, "session", force_return=True)
                if session and self.limit_prompt:
                    await session.send(self.limit_prompt)
            return self.success
        if self.success:
            self.last_time = datetime.now()
            return True


class Semaphore(JudgeAuxiliary):
    def __init__(self, count: int, limit_prompt: Optional[Union[str, MessageChain]] = None):
        self.count = count
        self.limit_prompt = limit_prompt
        self.semaphore = asyncio.Semaphore(count)
        super().__init__(priority=20)

    @property
    def id(self):
        return "entari.filter/access"

    @property
    def scopes(self):
        return {Scope.prepare, Scope.cleanup}

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if scope == Scope.prepare:
            if not await self.semaphore.acquire():
                session = await interface.query(Session, "session", force_return=True)
                if session and self.limit_prompt:
                    await session.send(self.limit_prompt)
                return False
            return True
        self.semaphore.release()
        return True
