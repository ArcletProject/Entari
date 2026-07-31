import asyncio
from datetime import datetime

from arclet.letoderea import STOP, Propagator, propagate
from arclet.letoderea.utils import TCallable
from ..message import MessageChain
from ..session import Session


class interval(Propagator):
    def __init__(self, value: float, limit_prompt: str | MessageChain | None = None, priority: int = 80):
        self.success = True
        self.value = value
        self.priority = priority
        self.limit_prompt = limit_prompt
        self.last_times: dict[str, datetime] = {}

    async def before(self, session: Session | None = None):
        session_id = (
            "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        )
        last_time = self.last_times.get(session_id, None)
        if not last_time:
            return
        self.success = (datetime.now() - last_time).total_seconds() > self.value
        if not self.success:
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self, session: Session | None = None):
        session_id = (
            "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        )
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
        session_id = (
            "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        )
        if session_id not in self.semaphores:
            self.semaphores[session_id] = asyncio.Semaphore(self.count)
        if not await self.semaphores[session_id].acquire():
            if session and self.limit_prompt:
                await session.send(self.limit_prompt)
            return STOP

    async def after(self, session: Session | None = None):
        session_id = (
            "$global" if not session else f"{session.account.platform}/{session.account.self_id}/{session.channel.id}"
        )
        if session_id not in self.semaphores:
            self.semaphores[session_id] = asyncio.Semaphore(self.count)
        self.semaphores[session_id].release()

    def compose(self):
        yield self.before, True, self.priority
        yield self.after, False, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)
