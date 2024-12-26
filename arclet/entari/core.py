from __future__ import annotations

from contextlib import suppress
import os

from arclet.letoderea import Contexts, Param, Provider, ProviderFactory, es, global_providers
from creart import it
from launart import Launart, Service
from satori import LoginStatus
from satori.client import App
from satori.client.account import Account
from satori.client.config import Config, WebhookInfo, WebsocketsInfo
from satori.client.protocol import ApiProtocol
from satori.model import Event
from tarina.generic import get_origin

from .config import EntariConfig
from .event.base import MessageCreatedEvent, event_parse
from .event.config import ConfigReload
from .event.lifespan import AccountUpdate
from .event.send import SendResponse
from .logger import log
from .plugin import load_plugin, plugin_config, requires
from .plugin.model import RootlessPlugin
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
            session = Session(context["account"], context["$event"])
            if "$message_content" in context:
                session.elements = context["$message_content"]
            if "$message_reply" in context:
                session.reply = context["$message_reply"]
            return session


class AccountProvider(Provider[Account]):
    async def __call__(self, context: Contexts):
        if "account" in context:
            return context["account"]


#
# class PluginProvider(Provider[Plugin]):
#     async def __call__(self, context: Contexts):
#         subscriber: Subscriber = context["$subscriber"]
#         func = subscriber.callable_target
#         if hasattr(func, "__globals__") and "__plugin__" in func.__globals__:  # type: ignore
#             return func.__globals__["__plugin__"]
#         if hasattr(func, "__module__"):
#             return plugin_service.plugins.get(func.__module__)


global_providers.extend([ApiProtocolProvider(), SessionProvider(), AccountProvider()])


@RootlessPlugin.apply("record_message")
def record(plg: RootlessPlugin):
    cfg = plugin_config()

    @plg.dispatch(MessageCreatedEvent).on(priority=0)
    async def log_msg(event: MessageCreatedEvent):
        log.message.info(
            f"[{event.channel.name or event.channel.id}] "
            f"{event.member.nick if event.member else (event.user.name or event.user.id)}"
            f"({event.user.id}) -> {event.message.content!r}"
        )

    if cfg.get("record_send", False):

        @plg.use(SendResponse)
        async def log_send(event: SendResponse):
            if event.session:
                log.message.info(
                    f"[{event.session.channel.name or event.session.channel.id}] <- {event.message.display()!r}"
                )
            else:
                log.message.info(f"[{event.channel}] <- {event.message.display()!r}")


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
        configs = []
        for conf in config.basic.get("network", []):
            if conf["type"] in ("websocket", "websockets", "ws"):
                configs.append(WebsocketsInfo(**{k: v for k, v in conf.items() if k != "type"}))
            elif conf["type"] in ("webhook", "wh", "http"):
                configs.append(WebhookInfo(**{k: v for k, v in conf.items() if k != "type"}))
        return cls(
            *configs,
            log_level=log_level,
            ignore_self_message=ignore_self_message,
        )

    def __init__(
        self,
        *configs: Config,
        log_level: str | int = "INFO",
        ignore_self_message: bool = True,
    ):
        from . import __version__

        log.core.opt(colors=True).info(f"Entari <b><c>version {__version__}</c></b>")
        super().__init__(*configs, default_api_cls=EntariProtocol)
        if not hasattr(EntariConfig, "instance"):
            EntariConfig.load()
        log.set_level(log_level)
        log.core.opt(colors=True).debug(f"Log level set to <y><c>{log_level}</c></y>")
        requires(*EntariConfig.instance.prelude_plugin)
        for plug in EntariConfig.instance.prelude_plugin:
            load_plugin(plug, prelude=True)
        plugins = [
            plug for plug in EntariConfig.instance.plugin if not plug.startswith("~") and not plug.startswith("$")
        ]
        requires(*plugins)
        for plug in plugins:
            load_plugin(plug)
        self.ignore_self_message = ignore_self_message
        self.register(self.handle_event)
        self.lifecycle(self.account_hook)
        self._ref_tasks = set()

        es.on(ConfigReload, self.reset_self)

    def reset_self(self, scope, key, value):
        if scope != "basic":
            return
        if key == "log_level":
            log.set_level(value)
            log.core.opt(colors=True).debug(f"Log level set to <y><c>{value}</c></y>")
        elif key == "ignore_self_message":
            self.ignore_self_message = value
        elif key == "network":
            for conn in self.connections:
                it(Launart).remove_component(conn)
            self.connections.clear()
            for conf in value:
                if conf["type"] in ("websocket", "websockets", "ws"):
                    self.apply(WebsocketsInfo(**{k: v for k, v in conf.items() if k != "type"}))
                elif conf["type"] in ("webhook", "wh", "http"):
                    self.apply(WebhookInfo(**{k: v for k, v in conf.items() if k != "type"}))
            for conn in self.connections:
                it(Launart).add_component(conn)

    def on_message(self, priority: int = 16):
        return es.on(MessageCreatedEvent, priority=priority)

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
        es.publish(AccountUpdate(account, state))

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
