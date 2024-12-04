from __future__ import annotations

import asyncio
from contextlib import suppress
import os

from arclet.letoderea import BaseAuxiliary, Contexts, Param, Provider, ProviderFactory, es, global_providers
from creart import it
from launart import Launart, Service
from satori import LoginStatus
from satori.client import App
from satori.client.account import Account
from satori.client.protocol import ApiProtocol
from satori.config import Config, WebhookInfo, WebsocketsInfo
from satori.model import Event
from tarina.generic import get_origin

from .command import _commands
from .config import EntariConfig
from .event.protocol import MessageCreatedEvent, event_parse
from .event.send import SendResponse
from .logger import log
from .plugin import load_plugin
from .plugin.service import plugin_service
from .session import EntariProtocol, Session


class ApiProtocolProvider(Provider[ApiProtocol]):
    async def __call__(self, context: Contexts):
        if account := context.get("account"):
            return account.protocol


class SessionProvider(Provider[Session]):
    def validate(self, param: Param):
        return get_origin(param.annotation) == Session

    async def __call__(self, context: Contexts):
        if "session" in context and isinstance(context["session"], Session):
            return context["session"]
        if "$origin_event" in context and "account" in context:
            return Session(context["account"], context["$event"])


class AccountProvider(Provider[Account]):
    async def __call__(self, context: Contexts):
        return context["account"]


global_providers.extend([ApiProtocolProvider(), SessionProvider(), AccountProvider()])


class Entari(App):
    id = "entari.service"

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None):
        return cls.from_config(EntariConfig.load(path))

    @classmethod
    def from_config(cls, config: EntariConfig | None = None):
        if not config:
            config = EntariConfig.instance
        ignore_self_message = config.basic.get("ignore_self_message", True)
        log_level = config.basic.get("log_level", "INFO")
        record_message = config.basic.get("record_message", False)
        configs = []
        for conf in config.basic.get("network", []):
            if conf["type"] in ("websocket", "websockets", "ws"):
                configs.append(WebsocketsInfo(**{k: v for k, v in conf.items() if k != "type"}))
            elif conf["type"] in ("webhook", "wh", "http"):
                configs.append(WebhookInfo(**{k: v for k, v in conf.items() if k != "type"}))
        return cls(
            *configs, log_level=log_level, ignore_self_message=ignore_self_message, record_message=record_message
        )

    def __init__(
        self,
        *configs: Config,
        log_level: str | int = "INFO",
        ignore_self_message: bool = True,
        record_message: bool = True,
    ):
        from . import __version__

        log.core.opt(colors=True).info(f"Entari <b><c>version {__version__}</c></b>")
        super().__init__(*configs, default_api_cls=EntariProtocol)
        if not hasattr(EntariConfig, "instance"):
            EntariConfig.load()
        log.set_level(log_level)
        for plug in EntariConfig.instance.plugin:
            load_plugin(plug)
        self.ignore_self_message = ignore_self_message
        es.register(_commands.publisher)
        self.register(self.handle_event)
        self.lifecycle(self.account_hook)
        self._ref_tasks = set()

        if record_message:

            @self.on_message(priority=0)
            async def log_msg(event: MessageCreatedEvent):
                log.message.info(
                    f"[{event.channel.name or event.channel.id}] "
                    f"{event.member.nick if event.member else (event.user.name or event.user.id)}"
                    f"({event.user.id}) -> {event.message.content!r}"
                )

            @es.use(SendResponse.__publisher__)
            async def log_send(event: SendResponse):
                if event.session:
                    log.message.info(f"[{event.session.channel.name or event.session.channel.id}] <- {event.message!r}")
                else:
                    log.message.info(f"[{event.channel}] <- {event.message!r}")

    def on(
        self,
        *events: type,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        return es.on(events, priority=priority, auxiliaries=auxiliaries, providers=providers)

    def on_message(
        self,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        return es.on(MessageCreatedEvent, priority=priority, auxiliaries=auxiliaries, providers=providers)

    def ensure_manager(self, manager: Launart):
        self.manager = manager
        manager.add_component(plugin_service)

    async def handle_event(self, account: Account, event: Event):
        with suppress(NotImplementedError):
            ev = event_parse(account, event)
            if self.ignore_self_message and isinstance(ev, MessageCreatedEvent) and ev.user.id == account.self_id:
                return
            es.publish(ev)
            return

        log.core.warning(f"received unsupported event {event.type}: {event}")

    async def account_hook(self, account: Account, state: LoginStatus):
        _connected = []
        _disconnected = []
        for plug in plugin_service.plugins.values():
            _connected.extend([func(account) for func in plug._connected])
            _disconnected.extend([func(account) for func in plug._disconnected])
        if state == LoginStatus.CONNECT:
            await asyncio.gather(*_connected, return_exceptions=True)
        elif state == LoginStatus.DISCONNECT:
            await asyncio.gather(*_disconnected, return_exceptions=True)

    @classmethod
    def current(cls):
        return it(Launart).get_component(cls)


class EntariProvider(Provider[Entari]):
    priority = 1

    async def __call__(self, context: Contexts):
        return Entari.current()


class LaunartProvider(Provider[Launart]):
    priority = 10

    async def __call__(self, context: Contexts):
        return it(Launart)


class ServiceProviderFactory(ProviderFactory):
    priority = 10

    class _Provider(Provider[Service]):
        def __init__(self, origin: type[Service]):
            super().__init__()
            self.origin = origin

        def validate(self, param: Param):
            anno = get_origin(param.annotation)
            return isinstance(anno, type) and issubclass(anno, self.origin)

        async def __call__(self, context: Contexts):
            return it(Launart).get_component(self.origin)

    def validate(self, param: Param):
        anno = get_origin(param.annotation)
        if isinstance(anno, type) and issubclass(anno, Service):
            return self._Provider(anno)


global_providers.extend([EntariProvider(), LaunartProvider(), ServiceProviderFactory()])  # type: ignore
