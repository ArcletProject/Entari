import asyncio
from typing import Generic, TYPE_CHECKING, Optional, Type, Dict, TypeVar
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
    running: bool

    def __init__(
            self,
            edoves: "Edoves",
            config: TConfig
    ):
        self.edoves = edoves
        self.network_protocol = config.get("protocol")(self, config)
        self.module_protocol = ModuleProtocol(self, self.network_protocol.identifier)
        self.monomer_protocol = MonomerProtocol(self, self.network_protocol.identifier)

    @property
    def modules(self):
        return self.module_protocol.storage

    @property
    def monomers(self):
        return self.monomer_protocol.storage

    @property
    def dockers(self):
        return self.network_protocol.storage

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

    def activate_modules(self, *module_type: Type[BaseModule]) -> None:
        """激活多个模块

        Args:
            module_type: 要激活的多个模块类型, 若有重复则重新激活
        """
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
        self.edoves.logger.info(f"{count} modules activate successful")

    async def start_running(self, interval: float = 0.02):
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
            await asyncio.sleep(interval)
            all_io: Dict[str, "InteractiveObject"] = {
                **self.module_protocol.storage,
                **self.monomer_protocol.storage,
                **self.network_protocol.storage
            }
            tasks = [
                asyncio.create_task(
                    v.behavior.update(), name=f"IO_Update @AllIO[{i}]"
                ) for i, v in enumerate(all_io.values()) if v.metadata.state not in (IOStatus.CLOSED, IOStatus.UNKNOWN)
            ]
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
            try:
                await v.behavior.quit()
            except NotImplementedError:
                self.edoves.logger.warning(f"{k}'s behavior start failed")
