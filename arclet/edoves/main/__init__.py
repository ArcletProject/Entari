import asyncio
import time
from typing import Dict, Generic, Optional, Union

from arclet.letoderea import EventSystem
import os
import json
from .protocol import ModuleProtocol
from .module import BaseModule
from .server_docker import BaseServerDocker
from .typings import TNProtocol, TConfig
from .exceptions import DataMissing, ValidationFailed
from ..utilles.logger import Logger
from .monomer import Monomer, BaseMonoBehavior, MonoMetaComponent
from ..builtin.medium import JsonMedium
from .scene import EdovesScene


class EdovesMetadata(MonoMetaComponent):
    io: "EdovesSelf"


class EdovesMainBehavior(BaseMonoBehavior):
    io: "EdovesSelf"
    loop: asyncio.AbstractEventLoop
    edoves: "Edoves"

    async def start(self):
        start_time = time.time()
        self.edoves.logger.info("Edoves Application Starting...")
        self.edoves.logger.info("this is start!")
        self.edoves.network_protocol.set_medium({"start": True})
        await self.edoves.network_protocol.broadcast_medium("DockerOperate", JsonMedium)
        self.edoves.logger.info(f"Edoves Application Started with {time.time() - start_time:.2}s")

    def activate(self):
        self.edoves = self.get_component(EdovesMetadata).protocol.scene.edoves
        self.edoves.scene.monomers.setdefault(self.io.metadata.identifier, self.io)
        self.loop = self.edoves.event_system.loop
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
            is_chat_log: bool = True,
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
            self.scene = EdovesScene(self, self.config)
            self.logger.info(f"{self.network_protocol.__class__.__name__} activate successful")
        except ValidationFailed:
            raise

        self.self = EdovesSelf(
            self.network_protocol,
            "Edoves Application",
            self.config.get("account"),
            "edoves"
        )
        if is_chat_log:
            from ..builtin.chatlog import ChatLogModule
            self.scene.activate_module(ChatLogModule)
        try:
            if sc := self.config.get("server_docker"):
                self.scene.dockers.setdefault(sc, sc(self.network_protocol, self.config.client()))
            else:
                from ..builtin.mah.server_docker import MAHServerDocker
                self.scene.dockers.setdefault(
                    MAHServerDocker, MAHServerDocker(self.network_protocol, self.config.client())
                )
            self.logger.info(f"{self.network_protocol.current.__class__.__name__} activate successful")
        except ValidationFailed:
            self.logger.warning(
                f"{self.network_protocol.current.__class__.__name__} does not supply the dock server you chosen")

    @property
    def network_protocol(self) -> TNProtocol:
        return self.scene.network_protocol

    @property
    def identifier(self) -> str:
        return self.scene.network_protocol.identifier

    def run(self):
        try:
            # if not self.running:
            #     self.running = True

            # self.daemon_task = loop.create_task(self.running_task(), name="cesloi_web_task")
            # while not self.bot_session.sessionKey:
            #     loop.run_until_complete(asyncio.sleep(0.001))
            # self.event_system.event_spread(ApplicationRunning(self))
            self.running_task = self.event_system.loop.create_task(
                self.scene.start_running(),
                name="Edoves_Loop_Task"
            )
            if self.running_task:
                self.event_system.loop.run_until_complete(self.running_task)
        # if self.daemon_task:
        #     loop.run_until_complete(self.daemon_task)
        except KeyboardInterrupt or asyncio.CancelledError:
            self.logger.warning("Interrupt detected, bot stopping ...")
        # loop.run_until_complete(self.close())

        self.logger.info("Edoves shutdown. Have a nice day!")
