from typing import Generic, TYPE_CHECKING, Optional, Type
from .protocol import ModuleProtocol, MonomerProtocol
from ..utilles import ModuleStatus
from .typings import TNProtocol
from .exceptions import ValidationFailed
from .module import MediumModule

if TYPE_CHECKING:
    from . import Edoves


class EdovesScene(Generic[TNProtocol]):
    edoves: "Edoves"
    module_protocol: ModuleProtocol
    monomer_protocol: MonomerProtocol
    network_protocol: TNProtocol

    def __init__(
            self,
            edoves: "Edoves",
    ):
        self.edoves = edoves
        self.network_protocol = edoves.network_protocol
        self.module_protocol = ModuleProtocol(self.edoves, self.edoves.identifier)
        self.monomer_protocol = MonomerProtocol(self.edoves, self.edoves.identifier)

    @property
    def modules(self):
        return self.module_protocol.storage

    @property
    def monomers(self):
        return self.monomer_protocol.storage

    def activate_module(self, module_type: Type[MediumModule]) -> Optional[MediumModule]:
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
            if new_module.metadata.state in (ModuleStatus.CLOSED, ModuleStatus.UNKNOWN):
                return
            self.modules.setdefault(module_type, new_module)
            self.edoves.logger.info(f"{_name} activate successful")
            return new_module
        except ValidationFailed:
            self.edoves.logger.warning(f"{_name} does not supply the dock server you chosen")

    def activate_modules(self, *module_type: Type[MediumModule]) -> None:
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
                if nm.metadata.state in (ModuleStatus.CLOSED, ModuleStatus.UNKNOWN):
                    return
                self.edoves.logger.debug(f"{_name} activate successful")
                count += 1
            except ValidationFailed:
                self.edoves.logger.warning(f"{_name} does not supply the dock server you chosen")
        self.edoves.logger.info(f"{count} modules activate successful")

    def setting_tasks(self):
        return (
            self.module_protocol.start_running(),
            self.monomer_protocol.start_running(),
            self.network_protocol.start_running()
        )
