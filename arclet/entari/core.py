from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from contextlib import suppress
import os
from pathlib import Path
import signal
import sys
from typing import get_args

from arclet.alconna import config as alconna_config
import arclet.letoderea as le
from arclet.letoderea import Contexts, Param, Provider, ProviderFactory, global_providers
from arclet.letoderea.scope import configure
from creart import it
from launart import Launart, Service
from satori import LoginStatus
from satori.client import App
from satori.client.account import Account
from satori.client.config import Config, WebhookInfo, WebsocketsInfo
from satori.client.protocol import ApiProtocol
from satori.model import Event
from tarina.generic import generic_isinstance, get_origin, is_optional

from .config import EntariConfig
from .config.file import LogInfo
from .config.model import config_model_validate
from .event.base import MessageCreatedEvent, event_parse
from .event.config import ConfigReload
from .event.lifespan import AccountUpdate
from .event.send import SendResponse
from .logger import apply_log_save, log
from .plugin import load_plugin, plugin_config, requires
from .plugin.model import RootlessPlugin
from .plugin.service import plugin_service
from .session import EntariProtocol, Session


class ApiProtocolProvider(Provider[ApiProtocol]):
    async def __call__(self, context: Contexts):
        if account := context.get("account"):
            return account.protocol


class SessionProviderFactory(ProviderFactory):
    class _SessionProvider(Provider[Session]):
        def __init__(self, target_type: type | None):
            super().__init__()
            self.target_type = target_type

        async def __call__(self, context: Contexts):
            if self.target_type and not generic_isinstance(context["$event"], self.target_type):
                return
            if "$session" in context and isinstance(context["$session"], Session):
                return context["$session"]
            if "$origin_event" in context and "account" in context:
                session = Session(context["account"], context["$event"])
                if "$message_content" in context:
                    session.elements = context["$message_content"]
                if "$message_reply" in context:
                    session.reply = context["$message_reply"]
                context["$session"] = session
                return session

    def validate(self, param: Param):
        if get_origin(param.annotation) is Session:
            args = get_args(param.annotation)
            return self._SessionProvider(args[0] if args else None)
        if is_optional(param.annotation, Session):
            args = get_args(get_args(param.annotation)[0])
            return self._SessionProvider(args[0] if args else None)


class AccountProvider(Provider[Account]):
    async def __call__(self, context: Contexts):
        if "account" in context:
            return context["account"]


global_providers.extend([ApiProtocolProvider(), SessionProviderFactory(), AccountProvider()])


@RootlessPlugin.apply("record_message", default=True)
def record(plg: RootlessPlugin):
    cfg = plugin_config()
    to_me_only = cfg.get("to_me_only", False)

    @plg.dispatch(MessageCreatedEvent).on(priority=0)
    async def log_msg(event: MessageCreatedEvent, is_notice_me: bool = False, is_reply_me: bool = False):
        if to_me_only and not is_notice_me and not is_reply_me:
            return
        log.message.info(
            f"[{event.channel.name or event.channel.id}] "
            f"{event.member.nick if event.member else (event.user.name or event.user.id)}"
            f"({event.user.id}) -> {event.message.content!r}"
        )

    if cfg.get("record_send", False):

        @plg.dispatch(SendResponse)
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
        ignore_self_message = config.basic.ignore_self_message
        log_level = config.basic.log.level
        skip_req_missing = config.basic.skip_req_missing
        external_dirs = config.basic.external_dirs
        configs = []
        for conf in config.basic.network:
            if conf["type"] in ("websocket", "websockets", "ws"):
                configs.append(WebsocketsInfo(**{k: v for k, v in conf.items() if k != "type"}))
            elif conf["type"] in ("webhook", "wh", "http"):
                configs.append(WebhookInfo(**{k: v for k, v in conf.items() if k != "type"}))
        return cls(
            *configs,
            log_level=log_level,
            ignore_self_message=ignore_self_message,
            skip_req_missing=skip_req_missing,
            external_dirs=external_dirs,
        )

    def __init__(
        self,
        *configs: Config,
        log_level: str | int = "INFO",
        ignore_self_message: bool = True,
        skip_req_missing: bool = False,
        external_dirs: Sequence[str | os.PathLike[str]] | None = None,
    ):
        from . import __version__

        configure(skip_req_missing=skip_req_missing)
        log.core.info(f"Entari <b><c>version {__version__}</c></b>")
        super().__init__(*configs, default_api_cls=EntariProtocol)
        if not hasattr(EntariConfig, "instance"):
            EntariConfig.load()
        alconna_config.command_max_count = EntariConfig.instance.basic.cmd_count
        log.set_level(log_level)
        self._log_save_dispose = lambda: None
        if EntariConfig.instance.basic.log.save:
            if EntariConfig.instance.basic.log.save is True:
                self._log_save_dispose = apply_log_save()
            else:
                self._log_save_dispose = apply_log_save(
                    rotation=EntariConfig.instance.basic.log.save.rotation,
                    compression=EntariConfig.instance.basic.log.save.compression,
                    colorize=EntariConfig.instance.basic.log.save.colorize,
                )
        log.ignores.update(EntariConfig.instance.basic.log.ignores)
        log.core.debug(f"Log level set to <y><c>{log_level}</c></y>")
        log.core.debug(f"Config loaded from <m>{EntariConfig.instance.path}</m>: <w>{EntariConfig.instance.data}</w>")
        self.ignore_self_message = ignore_self_message
        self.register(self.handle_event)
        self.lifecycle(self.account_hook)
        self._ref_tasks = set()

        le.on(ConfigReload, self.reset_self)

        self._path_scale = ()
        _external = [str(Path(d).resolve()) for d in external_dirs or []]
        if _external:
            sys.path.extend(_external)
            self._path_scale = (len(sys.path) - len(_external), len(sys.path))
            log.core.debug(f"Added external dirs: {_external}")

    @property
    def config(self):
        return EntariConfig.instance

    def reset_self(self, scope, key, value):
        if scope != "basic":
            return
        if key == "log_level":
            log.set_level(value)
            log.core.debug(f"Log level set to <y><c>{value}</c></y>")
        elif key == "log":
            new_conf = config_model_validate(LogInfo, value)
            log.set_level(new_conf.level)
            log.core.debug(f"Log level set to <y><c>{new_conf.level}</c></y>")
            log.ignores.clear()
            log.ignores.update(new_conf.ignores)
            self._log_save_dispose()
            if new_conf.save:
                if new_conf.save is True:
                    self._log_save_dispose = apply_log_save()
                else:
                    self._log_save_dispose = apply_log_save(
                        new_conf.save.rotation, new_conf.save.compression, new_conf.save.colorize
                    )
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
        elif key == "cmd_count":
            alconna_config.command_max_count = value
        elif key == "external_dirs":
            log.core.warning("External dirs cannot be changed at runtime, ignored.")

    def on_message(self, priority: int = 16):
        return le.on(MessageCreatedEvent, priority=priority)

    def ensure_manager(self, manager: Launart):
        self.manager = manager
        manager.add_component(plugin_service)

        requires(*EntariConfig.instance.prelude_plugin)
        for plug in EntariConfig.instance.prelude_plugin_names:
            load_plugin(plug, prelude=True)
        plugins = EntariConfig.instance.plugin_names
        requires(*plugins)
        for apply, slot in plugin_service._apply.items():
            if f"~{apply}" in EntariConfig.instance.plugin:
                continue
            if slot[1] and apply not in EntariConfig.instance.plugin:
                plugins.append(apply)
        for plug in plugins:
            load_plugin(plug)

    async def handle_event(self, account: Account, event: Event):
        with suppress(NotImplementedError):
            ev = event_parse(account, event)
            if self.ignore_self_message and isinstance(ev, MessageCreatedEvent) and ev.user.id == account.self_id:
                return
            le.publish(ev)
            return

        log.core.warning(f"received unsupported event {event.type}: {event}")

    async def account_hook(self, account: Account, state: LoginStatus):
        le.publish(AccountUpdate(account, state))

    def run(
        self,
        manager: Launart | None = None,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        stop_signal: Iterable[signal.Signals] = (signal.SIGINT,),
    ):
        super().run(manager, loop=loop, stop_signal=stop_signal)
        if self._path_scale:
            del sys.path[self._path_scale[0] : self._path_scale[1]]
        if EntariConfig.instance.path.exists():
            EntariConfig.instance.save()
        log.core.info("Entari Shutdown.")

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
            try:
                return it(Launart).get_component(self.origin)
            except ValueError:  # Service not loaded yet
                return

    def validate(self, param: Param):
        anno = get_origin(param.annotation)
        if isinstance(anno, type) and issubclass(anno, Service):
            return self._Provider(anno)
        if is_optional(param.annotation, Service):
            args = get_args(param.annotation)
            return self._Provider(args[0])


global_providers.extend([EntariProvider(), LaunartProvider(), ServiceProviderFactory()])  # type: ignore
le.es.set_event_loop(it(asyncio.AbstractEventLoop))
