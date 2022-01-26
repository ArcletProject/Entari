import asyncio
import importlib
from inspect import isclass, getmembers
from pathlib import Path
from typing import Generic, TYPE_CHECKING, Optional, Type, Dict, TypeVar, Union
from .protocol import ModuleProtocol, MonomerProtocol
from ..utilles import IOStatus
from .typings import TNProtocol, TConfig
from .exceptions import ValidationFailed
from .module import BaseModule

TMde = TypeVar("TMde", bound=BaseModule)

if TYPE_CHECKING:
    from . import Edoves
    from .interact import InteractiveObject


class EdovesScene(Generic[TNProtocol]):
    edoves: "Edoves"
    module_protocol: ModuleProtocol
    monomer_protocol: MonomerProtocol
    network_protocol: TNProtocol
    config: TConfig
    running: bool

    def __init__(
            self,
            edoves: "Edoves",
            config: TConfig
    ):
        self.edoves = edoves
        self.config = config
        self.network_protocol = config.get("protocol")(self, config)
        self.module_protocol = ModuleProtocol(self, self.network_protocol.identifier)
        self.monomer_protocol = MonomerProtocol(self, self.network_protocol.identifier)
        self.activate_modules(path=config.modules_path)

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
        self.monomers.clear()
        self.dockers.clear()

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
            self.edoves.logger.info(f"{_name} activate successful")
            return new_module
        except ValidationFailed:
            self.edoves.logger.warning(f"{_name} does not supply the dock server you chosen")

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
                self.edoves.logger.debug(f"{_name} activate successful")
                count += 1
            except ValidationFailed:
                self.edoves.logger.warning(f"{_name} does not supply the dock server you chosen")
        if count > 0:
            self.edoves.logger.info(f"{count} modules activate successful")
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
        all_io: Dict[str, "InteractiveObject"] = {
            **self.module_protocol.storage,
            **self.monomer_protocol.storage,
            **self.network_protocol.storage
        }
        for k, v in all_io.items():
            if v.metadata.state in (IOStatus.CLOSED, IOStatus.UNKNOWN):
                continue
            try:
                await v.behavior.start()
            except NotImplementedError:
                self.edoves.logger.warning(f"{k}'s behavior start failed")
        self.running = True
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
                    tasks.append(asyncio.create_task(v.behavior.update(), name=f"IO_Update @AllIO[{i}]"))
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
                    self.edoves.logger.warning(f"{k}'s behavior quit failed")

        self.clean_up()
