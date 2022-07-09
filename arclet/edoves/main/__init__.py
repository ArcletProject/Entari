import asyncio
import importlib.metadata
import time
from typing import Dict, Optional, Type, Tuple, Union
from arclet.letoderea import EventSystem
from .interact import IOManager
from .screen import Screen
from .protocol import AbstractProtocol
from .context import edoves_instance
from .network import NetworkStatus
from .config import TemplateConfig
from .exceptions import DataMissing, ValidationFailed
from .utilles import SceneStatus
from .utilles.logger import Logger, replace_traceback
from .utilles.security import check_name
from .interact.module import BaseModule
from .interact.server_docker import BaseServerDocker
from .interact.monomer import Monomer, MonoMetaComponent
from .scene import EdovesScene

AE_LOGO = "\n".join(
    (
        r"    _             _       _        ___     _                       ",
        r"   /_\  _ __ ____| | ____| |_     / __\ __| | _____   ______  ___  ",
        r"  //_\\| '_// ___| |/ __ \ __|   / __\ /__` |/ _ \ \ / / __ \/ __| ",
        r" /  _  \ | | (___| |  ___/ |_   / /__ |(__| | (_) \ V /  ___\___ \ ",
        r" \_/ \_/_|  \____|_|\____|\__|  \___/  \__,_|\___ /\_/ \____|____/ ",
        ""
    )
)


class Edoves:
    __instance: bool = False
    event_system: EventSystem
    logger: Logger.logger
    screen: Screen
    scene_list: Dict[str, EdovesScene] = {}
    protocol_list: Dict[Type[AbstractProtocol], AbstractProtocol] = {}

    def __init__(
            self,
            *,
            configs: Dict[str, Union[TemplateConfig, Tuple[Type[TemplateConfig], Dict]]],
            event_system: Optional[EventSystem] = None,
            debug: bool = False
    ):
        if self.__instance:
            return
        self.event_system: EventSystem = event_system or EventSystem()
        self.loop = self.event_system.loop
        self.logger = Logger(level='DEBUG' if debug else 'INFO').logger
        self.screen = Screen(self)
        replace_traceback(self.event_system.loop)

        for name, t_config in configs.items():
            try:
                check_name(name)
                cur_scene = EdovesScene(
                    name,
                    self.screen,
                    t_config[0].parse_obj(t_config[1]) if isinstance(t_config, tuple) else t_config
                )
                self.scene_list.setdefault(
                    name,
                    cur_scene
                )
            except ValidationFailed as e:
                self.logger.error(e)
            except ValueError as e:
                self.logger.critical(f"{e}: {name}")
                exit()
        self.__instance = True

    @classmethod
    def current(cls) -> 'Edoves':
        return edoves_instance.get()

    @classmethod
    def get_scene(cls, name: str) -> EdovesScene:
        return cls.scene_list.get(name)

    async def launch_task(self):
        self.logger.opt(colors=True, raw=True).info("=--------------------------------------------------------=\n")
        self.logger.opt(colors=True, raw=True).info(f"<cyan>{AE_LOGO}</>")
        official = []
        for dist in importlib.metadata.distributions():
            name: str = dist.metadata["Name"]
            version: str = dist.version
            if name.startswith("arclet-"):
                official.append((" ".join(name.split("-")[1:]).title(), version))

        for name, version in official:
            self.logger.opt(colors=True, raw=True).info(
                f"<magenta>{name}</> version: <yellow>{version}</>\n"
            )
        self.logger.opt(colors=True, raw=True).info("=--------------------------------------------------------=\n")
        all_time: float = 0
        self.logger.info("Edoves Application Start...")
        for name, cur_scene in self.scene_list.items():
            start_time = time.time()
            running_task = self.event_system.loop.create_task(
                cur_scene.start_running(),
                name=f"Edoves_{name}_Start_Task"
            )
            await running_task
            if cur_scene.status == SceneStatus.RUNNING:
                self.logger.debug(f"{name} Start Success")
                all_time += time.time() - start_time
        if all_time > 0:
            self.logger.info(f"Edoves Application Start Success, Total Running Time: {all_time:.2f}s")
        else:
            self.logger.error("Edoves Application Start Failed")
            raise KeyboardInterrupt

    async def daemon_task(self):
        self.logger.info("Edoves Application Running...")
        update_task = []
        for name, cur_scene in self.scene_list.items():
            running_task = self.event_system.loop.create_task(
                cur_scene.update(),
                name=f"Edoves_{name}_Running_Task"
            )
            update_task.append(running_task)
            self.logger.debug(f"{name} Running...")
        await asyncio.gather(*update_task)
        # await self.quit_task()

    async def quit_task(self):
        self.logger.info("Edoves Application Stop...")
        start_task = []
        for name, cur_scene in self.scene_list.items():
            running_task = self.event_system.loop.create_task(
                cur_scene.stop_running(),
                name=f"Edoves_{name}_Stop_Task"
            )
            start_task.append(running_task)
        await asyncio.gather(*start_task)
        self.logger.success("Edoves shutdown. Have a nice day!")
        IOManager.storage.clear()

    def run(self):
        try:
            self.event_system.loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            self.logger.warning("Interrupt detected, Edoves stopping ...")
            self.event_system.loop.run_until_complete(self.quit_task())

    async def start(self):
        await self.launch_task()
        await self.daemon_task()

    def __getitem__(self, item: str) -> EdovesScene:
        return self.scene_list.get(item)

    def __getattr__(self, item):
        if item in self.scene_list:
            return self.__getitem__(item)
        if item in self.protocol_list:
            return self.protocol_list[item]
        raise ValueError
