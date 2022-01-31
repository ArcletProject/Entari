import asyncio
import importlib
from inspect import isclass, getmembers
import shelve
from pathlib import Path
from typing import Generic, TYPE_CHECKING, Optional, Type, Dict, TypeVar, Union

from .monomer import MonoMetaComponent, Monomer
from .protocol import ModuleProtocol, MonomerProtocol
from ..builtin.behavior import MiddlewareBehavior
from ..builtin.medium import JsonMedium
from ..utilles import IOStatus
from .network import NetworkStatus
from .typings import TNProtocol, TConfig
from .exceptions import ValidationFailed
from .module import BaseModule
from .interact import InteractiveObject

TMde = TypeVar("TMde", bound=BaseModule)

if TYPE_CHECKING:
    from . import Edoves


class EdovesMetadata(MonoMetaComponent):
    io: "EdovesSelf"


class EdovesMainBehavior(MiddlewareBehavior):
    io: "EdovesSelf"
    loop: asyncio.AbstractEventLoop
    scene: "EdovesScene"

    async def start(self):
        await self.scene.network_protocol.set_medium({"start": True})
        await self.scene.network_protocol.broadcast_medium("DockerOperate", JsonMedium)
        while self.scene.network_protocol.current.metadata.state != NetworkStatus.CONNECTED:
            await asyncio.sleep(0.01)

    def activate(self):
        self.scene = self.get_component(EdovesMetadata).protocol.scene
        self.scene.monomers.setdefault(self.io.metadata.identifier, self.io)
        self.loop = self.scene.edoves.event_system.loop
        self.io.add_tags("bot", self.scene.network_protocol.source_information.name, "app")
        self.n_protocol = self.scene.network_protocol
        self.m_protocol = self.io.metadata.protocol


class EdovesSelf(Monomer):
    prefab_metadata = EdovesMetadata
    prefab_behavior = EdovesMainBehavior


class EdovesScene(Generic[TNProtocol]):
    scene_name: str
    protagonist: EdovesSelf
    edoves: "Edoves"
    module_protocol: ModuleProtocol
    monomer_protocol: MonomerProtocol
    network_protocol: TNProtocol
    config: TConfig
    running: bool

    def __init__(
            self,
            name: str,
            edoves: "Edoves",
            config: TConfig
    ):
        self.scene_name = name
        self.edoves = edoves
        self.config = config
        self.network_protocol = config.get("protocol")(self, config)
        self.module_protocol = ModuleProtocol(self, self.network_protocol.identifier)
        self.monomer_protocol = MonomerProtocol(self, self.network_protocol.identifier)
        self.cache_path = f"./edoves_cache/{self.network_protocol.source_information.name}"
        self.activate_modules(path=config.modules_path)

        self.protagonist = EdovesSelf(
            self.network_protocol,
            "Edoves Application",
            self.config.get("account"),
            "edoves"
        )
        try:
            if sc := self.config.get("server_docker"):
                self.dockers.setdefault(sc, sc(self.network_protocol, self.config.client()))
            else:
                from ..builtin.mah.server_docker import MAHServerDocker
                self.dockers.setdefault(
                    MAHServerDocker, MAHServerDocker(self.network_protocol, self.config.client())
                )
            self.edoves.logger.info(
                f"{self.scene_name}: "
                f"{self.network_protocol.current.__class__.__name__} activate successful"
            )
        except ValidationFailed:
            self.edoves.logger.warning(
                f"{self.scene_name}: "
                f"{self.network_protocol.current.__class__.__name__} does not supply the dock server you chosen"
            )

    @property
    def modules(self):
        return self.module_protocol.storage

    @property
    def monomers(self):
        return self.monomer_protocol.storage

    @property
    def dockers(self):
        return self.network_protocol.storage

    def clean_up(self):
        self.modules.clear()
        self.dockers.clear()
        self.save_snap()

    def save_snap(self):
        path = Path(self.cache_path)
        if not path.exists():
            path.mkdir()
        relation_table = {}
        for i, m in self.monomers.items():
            relation_table[i] = {'parents': list(m.parents.keys()), 'children': list(m.children.keys())}
        monomers = {k: v for k, v in self.monomers.items() if k != str(self.config.account)}
        with shelve.open(f"{self.cache_path}/monomerSnap.db") as db:
            db['rtable'] = relation_table
            db['monomer'] = monomers

    def load_snap(self):
        try:
            with shelve.open(f"{self.cache_path}/monomerSnap.db") as db:
                try:
                    self.monomer_protocol.storage.update(db['monomer'])
                    r_table = db['rtable']
                except KeyError:
                    return
                for i, r in r_table.items():
                    m = self.monomers.get(i)
                    for ri in r['parents']:
                        m.set_parent(self.monomers[ri])
                    for ri in r['children']:
                        m.set_child(self.monomers[ri])
        except FileNotFoundError:
            return

    def activate_module(self, module_type: Type[TMde]) -> Optional[TMde]:
        """激活单个模块并返回

        Args:
            module_type: 要激活的模块类型
        Returns:
            new_module: 激活完成的模块
        """
        _name = module_type.__name__
        if m := self.modules.get(module_type):
            return m
        try:
            new_module = module_type(self.module_protocol)
            if new_module.metadata.state in (IOStatus.CLOSED, IOStatus.UNKNOWN):
                return
            self.modules.setdefault(module_type, new_module)
            self.edoves.logger.info(f"{self.scene_name}: {_name} activate successful")
            return new_module
        except ValidationFailed:
            self.edoves.logger.warning(f"{self.scene_name}: {_name} does not supply the dock server you chosen")

    def activate_modules(self, *module_type: Type[BaseModule], path: Optional[Union[str, Path]] = None) -> None:
        """激活多个模块

        Args:
            module_type: 要激活的多个模块类型, 若有重复则重新激活
            path: 文件路径, 可以是文件夹路径
        """

        def __path_import(scene_self, path_parts):
            mdle = importlib.import_module(".".join(path_parts).replace(".py", ""))
            for n, m in getmembers(
                    mdle, lambda x: isclass(x) and issubclass(x, BaseModule) and x is not BaseModule
            ):
                scene_self.activate_module(m)

        count = 0
        for mt in module_type:
            _name = mt.__name__
            try:
                _name = mt.__name__
                nm = mt(self.module_protocol)
                self.modules.setdefault(mt, nm)
                if nm.metadata.state in (IOStatus.CLOSED, IOStatus.UNKNOWN):
                    return
                self.edoves.logger.debug(f"{self.scene_name}: {_name} activate successful")
                count += 1
            except ValidationFailed:
                self.edoves.logger.warning(f"{self.scene_name}: {_name} does not supply the dock server you chosen")
        if count > 0:
            self.edoves.logger.info(f"{self.scene_name}: {count} modules activate successful")
        if path:
            ignore = ["__init__.py", "__pycache__"]
            path = path if isinstance(path, Path) else Path(path)
            if path.is_dir():
                for p in path.iterdir():
                    try:
                        if p.parts[-1] in ignore:
                            continue
                        __path_import(self, p.parts)
                    except ModuleNotFoundError:
                        continue
            else:
                try:
                    __path_import(self, path.parts)
                except ModuleNotFoundError:
                    pass

    async def start_running(self):
        self.load_snap()
        self.running = True
        self.edoves.logger.info(f"Using DataSource: {self.network_protocol.source_information.info}")
        all_io: Dict[str, "InteractiveObject"] = {

            **self.monomer_protocol.storage,
            **self.network_protocol.storage,
            **self.module_protocol.storage,
        }
        tasks = []
        for i, v in enumerate(all_io.values()):
            if v.metadata.state in (IOStatus.CLOSED, IOStatus.UNKNOWN):
                continue
            tasks.append(asyncio.create_task(v.behavior.start(), name=f"{self.scene_name}_IO_Start @AllIO[{i}]"))

        try:
            results = await asyncio.gather(*tasks)
            for task in results:
                if task and task.exception() == NotImplementedError:
                    self.edoves.logger.warning(f"{task}'s behavior in {self.scene_name} start failed.")
        except TimeoutError:
            await self.stop_running()
            return
        await asyncio.sleep(0.001)
        self.edoves.logger.info(f"{len(all_io)} InteractiveObjects in {self.scene_name} has been loaded.")

    async def update(self):
        while self.running:
            await asyncio.sleep(self.config.update_interval)
            all_io: Dict[str, "InteractiveObject"] = {
                **self.module_protocol.storage,
                **self.monomer_protocol.storage,
                **self.network_protocol.storage
            }
            tasks = []
            for i, v in enumerate(all_io.values()):
                if v.metadata.state == IOStatus.CLOSE_WAIT:
                    v.metadata.state = IOStatus.CLOSED
                if v.metadata.state not in (IOStatus.CLOSED, IOStatus.UNKNOWN):
                    tasks.append(asyncio.create_task(
                        v.behavior.update(), name=f"{self.scene_name}_IO_Update @AllIO[{i}]"
                    ))
            try:
                await asyncio.gather(*tasks)
            except NotImplementedError:
                pass

    async def stop_running(self):
        self.running = False
        all_io: Dict[str, "InteractiveObject"] = {
            **self.module_protocol.storage,
            **self.monomer_protocol.storage,
            **self.network_protocol.storage
        }
        for k, v in all_io.items():
            if v.metadata.state not in (IOStatus.CLOSED, IOStatus.UNKNOWN):
                try:
                    v.metadata.state = IOStatus.CLOSED
                    await v.behavior.quit()
                except NotImplementedError:
                    self.edoves.logger.warning(f"{k}'s behavior in {self.scene_name} quit failed.")

        self.clean_up()
