from __future__ import annotations

import asyncio
from contextlib import suppress

from arclet.letoderea import (
    BaseAuxiliary,
    Contexts,
    EventSystem,
    Param,
    Provider,
    ProviderFactory,
    global_providers,
)
from loguru import logger
from satori.client import App
from satori.client.account import Account
from satori.client.protocol import ApiProtocol
from satori.config import Config
from satori.model import Event
from tarina.generic import get_origin

from .event import MessageEvent, event_parse
from .plugin import dispatchers
from .session import Session


class ApiProtocolProvider(Provider[ApiProtocol]):
    async def __call__(self, context: Contexts):
        if account := context.get("$account"):
            return account.protocol


class SessionProvider(Provider[Session]):
    def validate(self, param: Param):
        return get_origin(param.annotation) == Session

    async def __call__(self, context: Contexts):
        if "$origin_event" in context and "$account" in context:
            return Session(context["$account"], context["$event"])


global_providers.extend([ApiProtocolProvider(), SessionProvider()])


class Entari(App):
    id = "entari.service"

    def __init__(self, *configs: Config):
        super().__init__(*configs)
        self.event_system = EventSystem()
        self.register(self.handle_event)
        self._ref_tasks = set()

    def on(
        self,
        *events: type,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        return self.event_system.on(*events, priority=priority, auxiliaries=auxiliaries, providers=providers)

    def on_message(
        self,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        return self.event_system.on(
            MessageEvent, priority=priority, auxiliaries=auxiliaries, providers=providers
        )

    async def handle_event(self, account: Account, event: Event):
        async def event_parse_task(connection: Account, raw: Event):
            loop = asyncio.get_running_loop()
            with suppress(NotImplementedError):
                ev = event_parse(connection, raw)
                self.event_system.publish(ev)
                for disp in dispatchers.values():
                    if not disp.validate(ev):
                        continue
                    task = loop.create_task(disp.publish(ev))
                    self._ref_tasks.add(task)
                    task.add_done_callback(self._ref_tasks.discard)
                return

            logger.warning(f"received unsupported event {raw.type}: {raw}")

        await event_parse_task(account, event)
