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
from launart import Launart
from loguru import logger
from satori import LoginStatus
from satori.client import App
from satori.client.account import Account
from satori.client.protocol import ApiProtocol
from satori.config import Config
from satori.model import Event
from tarina.generic import get_origin

from .command import _commands
from .event import MessageEvent, event_parse
from .plugin.service import service
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
        self.event_system.register(_commands.publisher)
        self.register(self.handle_event)
        self.lifecycle(self.account_hook)
        self._ref_tasks = set()

        @self.on_message(priority=0)
        def log(event: MessageEvent):
            logger.info(
                f"[{event.channel.name or event.channel.id}] "
                f"{event.member.nick if event.member else (event.user.name or event.user.id)}"
                f"({event.user.id}) -> {event.message.content!r}"
            )

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

    def ensure_manager(self, manager: Launart):
        self.manager = manager
        manager.add_component(service)

    async def handle_event(self, account: Account, event: Event):
        async def event_parse_task(connection: Account, raw: Event):
            loop = asyncio.get_running_loop()
            with suppress(NotImplementedError):
                ev = event_parse(connection, raw)
                self.event_system.publish(ev)
                for plugin in service.plugins.values():
                    for disp in plugin.dispatchers.values():
                        if not disp.validate(ev):
                            continue
                        if disp._run_by_system:
                            continue
                        task = loop.create_task(disp.publish(ev))
                        self._ref_tasks.add(task)
                        task.add_done_callback(self._ref_tasks.discard)
                return

            logger.warning(f"received unsupported event {raw.type}: {raw}")

        await event_parse_task(account, event)

    async def account_hook(self, account: Account, state: LoginStatus):
        _connected = []
        _disconnected = []
        for plug in service.plugins.values():
            _connected.extend([func(account) for func in plug._connected])
            _disconnected.extend([func(account) for func in plug._disconnected])
        if state == LoginStatus.CONNECT:
            await asyncio.gather(*_connected, return_exceptions=True)
        elif state == LoginStatus.DISCONNECT:
            await asyncio.gather(*_disconnected, return_exceptions=True)
