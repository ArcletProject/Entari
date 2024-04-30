from __future__ import annotations

import asyncio
from contextlib import suppress

from arclet.letoderea import Contexts, EventSystem, Provider, global_providers
from loguru import logger
from satori.client import App
from satori.client.account import Account
from satori.client.session import Session
from satori.config import Config
from satori.model import Event

from .event import event_parse
from .plugin import dispatchers
from .session import ContextSession


class SessionProvider(Provider[Session]):
    async def __call__(self, context: Contexts):
        if account := context.get("$account"):
            return account.session


class ContextSessionProvider(Provider[ContextSession]):
    async def __call__(self, context: Contexts):
        if "$origin_event" and "$account" in context:
            return ContextSession(context["$account"], context["$origin_event"])


global_providers.extend([SessionProvider(), ContextSessionProvider()])


class Entari(App):
    id = "entari.service"

    def __init__(self, *configs: Config):
        super().__init__(*configs)
        self.event_system = EventSystem()
        self.register(self.handle_event)
        self._ref_tasks = set()
        # self.lifecycle(self.handle_lifecycle)

    async def handle_event(self, account: Account, event: Event):
        async def event_parse_task(connection: Account, raw: Event):
            loop = asyncio.get_running_loop()
            with suppress(NotImplementedError):
                ev = event_parse(connection, raw)
                self.event_system.publish(ev)
                for disp in dispatchers.values():
                    task = loop.create_task(disp.publish(ev))
                    self._ref_tasks.add(task)
                    task.add_done_callback(self._ref_tasks.discard)
                return

            logger.warning(f"received unsupported event {raw.type}: {raw}")

        await event_parse_task(account, event)

    # async def handle_lifecycle(self, account: Account, state: LoginStatus):
    # if state == LoginStatus.ONLINE:
    #     route = Selector().land(account.platform).account(account.self_id)
    #     _account = SatoriAccount(route, self.protocol)
    #     self.protocol.avilla.accounts[route] = AccountInfo(
    #         route, _account, self.protocol, platform(account.platform)
    #     )
    #     self.protocol.avilla.broadcast.postEvent(AccountRegistered(self.protocol.avilla, _account))
    #     self._accounts[account.identity] = _account
    #     _account.client = account
    # elif state == LoginStatus.CONNECT:
    #     _account = self._accounts[account.identity]
    #     self.protocol.avilla.broadcast.postEvent(AccountAvailable(self.protocol.avilla, _account))
    #     _account.client = account
    #     _account.status.enabled = True
    # elif state == LoginStatus.DISCONNECT:
    #     _account = self._accounts[account.identity]
    #     _account.status.enabled = False
    #     self.protocol.avilla.broadcast.postEvent(AccountUnavailable(self.protocol.avilla, _account))
    # elif state == LoginStatus.OFFLINE:
    #     _account = self._accounts[account.identity]
    #     _account.status.enabled = False
    #     self.protocol.avilla.broadcast.postEvent(AccountUnregistered(self.protocol.avilla, _account))
    #     with suppress(KeyError):
    #         del self._accounts[account.identity]
    #         del self.protocol.avilla.accounts[_account.route]
