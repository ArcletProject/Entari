import asyncio
import time
from typing import Dict, Generic, Optional, Union, Type

from ...letoderea import EventSystem
import os
import json
from .protocol import ModuleProtocol
from .module import MediumModule
from .server_docker import BaseServerDocker
from .typings import TNProtocol, TConfig
from .exceptions import DataMissing, ValidationFailed
from ..utilles.logger import Logger
from .monomer import Monomer, BaseMonoBehavior, MonoMetaComponent

from .scene import EdovesScene


class EdovesMetadata(MonoMetaComponent):
    io: "EdovesSelf"
    edoves: "Edoves"


class EdovesMainBehavior(BaseMonoBehavior):
    io: "EdovesSelf"
    loop: asyncio.AbstractEventLoop
    data: EdovesMetadata

    async def start(self):
        start_time = time.time()
        self.data.edoves.logger.info("Edoves Application Starting...")
        self.data.edoves.logger.info("this is start!")
        self.data.protocol.set_medium({
            "start": True
        })
        self.data.edoves.logger.info(f"Edoves Application Started with {time.time() - start_time:.2}s")

    def activate(self):
        self.data = self.get_component(EdovesMetadata)
        self.data.edoves = self.data.protocol.edoves
        self.loop = self.data.edoves.event_system.loop
        self.io.add_tags("bot", "Edoves", "app")


class EdovesSelf(Monomer):
    prefab_metadata = EdovesMetadata
    prefab_behavior = EdovesMainBehavior


class Edoves(Generic[TConfig]):
    event_system: EventSystem
    logger: Logger.logger
    config: TConfig
    scene: EdovesScene
    self: EdovesSelf

    def __init__(
            self,
            *,
            event_system: Optional[EventSystem] = None,
            logger: Optional[Logger] = None,
            debug: bool = False,
            config: TConfig = None,
            profile: Optional[Union[str, Dict]] = None
    ):
        self.event_system: EventSystem = event_system or EventSystem()
        self.logger = logger or Logger(level='DEBUG' if debug else 'INFO').logger
        if config:
            self.config = config
        elif profile:
            from ..builtin.mah import MAHConfig
            if isinstance(profile, Dict):
                self.config = MAHConfig.parse_obj(profile)
            else:
                if os.path.exists(profile):
                    with open(profile, 'r+', encoding='UTF-8') as f_obj:
                        config_data = json.load(f_obj)
                        self.config = MAHConfig.parse_obj(config_data)
                else:
                    raise Exception('没有有效文件！')
        else:
            raise DataMissing("配置文件缺失！")
        try:
            self.self = EdovesSelf(
                self.config.get("protocol")(self, self.config),
                "Edoves Application",
                self.config.get("account"),
                "edoves"
            )
            self.logger.info(f"{self.network_protocol.__class__.__name__} activate successful")
        except ValidationFailed:
            raise

        self.scene = EdovesScene(self)
        self.scene.monomers.setdefault(self.self.metadata.identifier, self.self)

        try:
            if sc := self.config.get("server_docker"):
                self.network_protocol.storage.setdefault(sc, sc(self.network_protocol, self.config.client()))
            else:
                from ..builtin.mah.server_docker import MAHServerDocker
                self.network_protocol.storage.setdefault(
                    MAHServerDocker, MAHServerDocker(self.network_protocol, self.config.client())
                )
            self.logger.info(f"{self.network_protocol.current.__class__.__name__} activate successful")
        except ValidationFailed:
            self.logger.warning(
                f"{self.network_protocol.current.__class__.__name__} does not supply the dock server you chosen")

    @property
    def network_protocol(self) -> TNProtocol:
        return self.self.metadata.protocol

    @property
    def identifier(self) -> str:
        return self.self.metadata.protocol.identifier

    def run(self):
        try:
            # if not self.running:
            #     self.running = True

            # self.daemon_task = loop.create_task(self.running_task(), name="cesloi_web_task")
            # while not self.bot_session.sessionKey:
            #     loop.run_until_complete(asyncio.sleep(0.001))
            # self.event_system.event_spread(ApplicationRunning(self))
            self.running_task = self.event_system.loop.create_task(self.scene.start_running())
            if self.running_task:
                self.event_system.loop.run_until_complete(self.running_task)
        # if self.daemon_task:
        #     loop.run_until_complete(self.daemon_task)
        except KeyboardInterrupt or asyncio.CancelledError:
            self.logger.warning("Interrupt detected, bot stopping ...")
        # loop.run_until_complete(self.close())

        self.logger.info("Edoves shutdown. Have a nice day!")
