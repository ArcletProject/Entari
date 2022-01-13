import asyncio
import time
from typing import Dict, Generic, Optional, Union, Type
from arclet.letoderea import EventSystem
import os
import json
from .protocol import ModuleProtocol
from .module import MediumModule
from .server_docker import BaseServerDocker
from .typings import TNProtocol, TConfig
from .exceptions import DataMissing, ValidationFailed
from ..logger import Logger
from ..utilles import ModuleStatus
from .controller import Controller
from .monomer import Monomer


class Edoves(Generic[TNProtocol, TConfig]):
    event_system: EventSystem
    loop: asyncio.AbstractEventLoop
    module_protocol: ModuleProtocol
    config: TConfig
    server_docker: BaseServerDocker
    self: Monomer
    monomer_controller: Controller[int, Monomer]

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
        self.loop = self.event_system.loop
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
            raise DataMissing("配置文件缺失！")

        self.self = Monomer(self.config.get("protocol")(self, self.config), "Edoves Application")
        self.self.identifier = self.config.get("account")
        self.module_protocol = ModuleProtocol(self, self.identifier)
        self.logger.info(f"{self.network_protocol.__class__.__name__} activate successful")

        try:
            if sc := self.config.get("server_docker"):
                self.server_docker = sc(self.network_protocol)
            else:
                from edoves.builtin.mah import MAHConfig
                self.server_docker = MAHConfig.dock_server(self.network_protocol)
            self.logger.info(f"{self.server_docker.__class__.__name__} activate successful")
        except ValidationFailed:
            self.logger.warning(
                f"{self.network_protocol.__class__.__name__} does not supply the dock server you chosen")

        self.monomer_controller = Controller(self)
        self.monomer_controller.add(self.self.identifier, self.self)

    @property
    def network_protocol(self) -> TNProtocol:
        return self.self.protocol

    @property
    def identifier(self) -> int:
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
        _name = module_type.__name__
        if m := self.module_protocol.modules.get(module_type):
            return m
        try:
            new_module = module_type(self.module_protocol)
            self.module_protocol.modules.add(module_type, new_module)
            self.logger.info(f"{_name} activate successful")
            return new_module
        except ValidationFailed:
            self.logger.warning(f"{_name} does not supply the dock server you chosen")

    def activate_modules(self, *module_type: Type[MediumModule]) -> None:
        """激活多个模块

        Args:
            module_type: 要激活的多个模块类型, 若有重复则重新激活
        """
        count = 0
        for mt in module_type:
            if mt.state in (ModuleStatus.CLOSED, ModuleStatus.UNKNOWN):
                continue
            _name = mt.__name__
            try:
                _name = mt.__name__
                self.module_protocol.modules.add(mt, mt(self.module_protocol))
                self.logger.debug(f"{_name} activate successful")
                count += 1
            except ValidationFailed:
                self.logger.warning(f"{_name} does not supply the dock server you chosen")
        self.logger.info(f"{count} modules activate successful")

    def run(self):
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
