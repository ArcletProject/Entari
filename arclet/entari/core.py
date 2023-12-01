from __future__ import annotations

import asyncio
from contextlib import suppress

from loguru import logger
from satori.client.account import Account
from satori.client import App
from satori.model import Event, LoginStatus


class Entari(App):
    id = "entari.service"

    def __init__(self):
        super().__init__()
        self.register(self.handle_event)
        self.lifecycle(self.handle_lifecycle)

    async def handle_event(self, account: Account, event: Event):
        async def event_parse_task(connection: Account, raw: Event):
            with suppress(NotImplementedError):
                await SatoriCapability(self.staff.ext({"connection": connection})).handle_event(raw)
                return

            logger.warning(f"received unsupported event {raw.type}: {raw}")

        asyncio.create_task(event_parse_task(account, event))

    async def handle_lifecycle(self, account: Account, state: LoginStatus):
        if state == LoginStatus.ONLINE:
            route = Selector().land(account.platform).account(account.self_id)
            _account = SatoriAccount(route, self.protocol)
            self.protocol.avilla.accounts[route] = AccountInfo(
                route, _account, self.protocol, platform(account.platform)
            )
            self.protocol.avilla.broadcast.postEvent(AccountRegistered(self.protocol.avilla, _account))
            self._accounts[account.identity] = _account
            _account.client = account
        elif state == LoginStatus.CONNECT:
            _account = self._accounts[account.identity]
            self.protocol.avilla.broadcast.postEvent(AccountAvailable(self.protocol.avilla, _account))
            _account.client = account
            _account.status.enabled = True
        elif state == LoginStatus.DISCONNECT:
            _account = self._accounts[account.identity]
            _account.status.enabled = False
            self.protocol.avilla.broadcast.postEvent(AccountUnavailable(self.protocol.avilla, _account))
        elif state == LoginStatus.OFFLINE:
            _account = self._accounts[account.identity]
            _account.status.enabled = False
            self.protocol.avilla.broadcast.postEvent(AccountUnregistered(self.protocol.avilla, _account))
            with suppress(KeyError):
                del self._accounts[account.identity]
                del self.protocol.avilla.accounts[_account.route]
