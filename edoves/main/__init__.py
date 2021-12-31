import asyncio
import time
from typing import Dict, Generic, Optional, Union, Type
from arclet.letoderea import EventSystem
import os
import json
from .protocol import ModuleProtocol
from .module import MediumModule
from .dock_server import BaseDockServer
from .typings import TNProtocol, TConfig
from .exceptions import DataMissing, ValidationFailed
from ..logger import Logger
from ..utilles import ModuleStatus
from .monomer import Monomer


class Edoves(Generic[TNProtocol, TConfig]):
    module_protocol: ModuleProtocol
    config: TConfig
    dock_server: BaseDockServer
    modules: Dict[Type[MediumModule], MediumModule]
    event_system: EventSystem
    self: Monomer

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
            from edoves.builtin.mah import MAHConfig
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
            raise DataMissing
        self._init_protocol()
        self._init_modules()

    def _init_modules(self):
        self.modules = {}
        try:
            if self.config.get("dock_server"):
                self.dock_server = self.config.get("dock_server")(self.network_protocol)
            else:
                from edoves.builtin.mah import MAHConfig
                self.dock_server = MAHConfig.dock_server(self.network_protocol)
        except ValidationFailed:
            self.logger.warning(
                f"{self.network_protocol.__class__.__name__} does not supply the dock server you chosen")
            raise
        self.logger.info(f"{self.dock_server.__class__.__name__} activate successful")

    def _init_protocol(self):
        self.self = Monomer(self.config.get("protocol")(self, self.config), "Edoves Application")
        self.self.identifier = self.config.get("account")
        self.module_protocol = ModuleProtocol(self, self.identifier)
        self.logger.info(f"{self.network_protocol.__class__.__name__} activate successful")

    @property
    def network_protocol(self):
        return self.self.protocol

    @property
    def identifier(self):
        return self.self.protocol.identifier

    def activate_module(self, module_type: Type[MediumModule]) -> Optional[MediumModule]:
        """激活单个模块并返回

        Args:
            module_type: 要激活的模块类型
        Returns:
            new_module: 激活完成的模块
        """
        if module_type.state in (ModuleStatus.CLOSED, ModuleStatus.UNKNOWN):
            return
        if self.modules.get(module_type):
            return self.modules[module_type]
        try:
            new_module = module_type(self.module_protocol)
            self.modules[module_type] = new_module
            self.logger.info(f"{new_module.__name__} activate successful")
            return new_module
        except ValidationFailed:
            self.logger.warning(f"{module_type.__name__} does not supply the dock server you chosen")
            raise

    def activate_modules(self, *module_type: Type[MediumModule]) -> None:
        """激活多个模块

        Args:
            module_type: 要激活的多个模块类型, 若有重复则重新激活
        """
        count = 0
        for mt in module_type:
            if mt.state in (ModuleStatus.CLOSED, ModuleStatus.UNKNOWN):
                continue
            try:
                self.modules[mt] = mt(self.module_protocol)
                self.logger.debug(f"{mt.__name__} activate successful")
                count += 1
            except ValidationFailed:
                self.logger.warning(f"{module_type.__name__} does not supply the dock server you chosen")
                raise
        self.logger.info(f"{count} modules activate successful")

    def run(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if self.event_system:
            loop = self.event_system.loop
        else:
            loop = loop or asyncio.get_event_loop()

        try:
            # if not self.running:
            #     self.running = True
            start_time = time.time()
            self.logger.info("Edoves Application Starting...")
            # self.daemon_task = loop.create_task(self.running_task(), name="cesloi_web_task")
            # while not self.bot_session.sessionKey:
            #     loop.run_until_complete(asyncio.sleep(0.001))
            # self.event_system.event_spread(ApplicationRunning(self))
            self.logger.info(f"Edoves Application Started with {time.time() - start_time:.2}s")

        # if self.daemon_task:
        #     loop.run_until_complete(self.daemon_task)
        except KeyboardInterrupt or asyncio.CancelledError:
            self.logger.warning("Interrupt detected, bot stopping ...")
        # loop.run_until_complete(self.close())
        self.logger.info("Edoves shutdown. Have a nice day!")
