import asyncio
from abc import ABCMeta, abstractmethod
from asyncio import Event
from typing import TYPE_CHECKING, Optional, Union, Type, TypeVar, Dict
from .medium import BaseMedium
from ..utilles.security import UNDEFINED
from ..utilles.data_source_info import DataSourceInfo
from ..utilles import ModuleStatus
from .exceptions import ValidationFailed, DataMissing
from .typings import TData

TM = TypeVar("TM", bound=BaseMedium)


if TYPE_CHECKING:
    from . import Edoves
    from .config import TemplateConfig
    from .interact import InteractiveObject
    from .module import BaseModule, MediumModule
    from .server_docker import BaseServerDocker
    from .monomer import Monomer


class AbstractProtocol(metaclass=ABCMeta):
    edoves: "Edoves"
    medium: TData
    storage: Dict[Type["InteractiveObject"], "InteractiveObject"]
    __identifier: str = UNDEFINED

    def __init__(self, edoves: "Edoves", identifier: str = None):
        self.edoves = edoves
        if not identifier and self.__identifier == UNDEFINED:
            raise ValidationFailed
        else:
            self.__identifier = identifier
        self.storage = {}
        self.medium_ev: Event = asyncio.Event()

    @property
    def identifier(self):
        return self.__identifier

    @property
    def current(self):
        return list(self.storage.values())[-1]

    def verify(self, other: Union[int, "BaseModule"]):
        if isinstance(other, int) and other != self.edoves.identifier:
            raise ValidationFailed
        if other.metadata.identifier != str(self.edoves.identifier):
            other.metadata.state = ModuleStatus.CLOSED
            raise ValidationFailed

    async def get_medium(self, medium_type: Optional[Type[TM]]) -> Union[TM, TData]:
        if not self.medium:
            await self.medium_ev.wait()
        self.medium_ev.clear()
        if medium_type and not isinstance(self.medium, medium_type):
            return medium_type.create(self.edoves.self, Dict)(self.medium)
        return self.medium

    def set_medium(self, medium: Union[TM, TData]):
        self.medium = medium
        self.medium_ev.set()

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}>"
        )


class ModuleProtocol(AbstractProtocol):
    storage: Dict[Type["MediumModule"], "MediumModule"]
    medium: BaseMedium

    def __init__(self, edoves: "Edoves", identifier: str):
        super().__init__(edoves, identifier)


class MonomerProtocol(AbstractProtocol):
    storage: Dict[int, "Monomer"]

    def __init__(self, edoves: "Edoves", identifier: str):
        super().__init__(edoves, identifier)


class NetworkProtocol(AbstractProtocol):
    storage: Dict[Type["BaseServerDocker"], "BaseServerDocker"]
    source_information: DataSourceInfo
    config: "TemplateConfig"

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "source_information"):
            raise DataMissing
        return super(NetworkProtocol, cls).__new__(cls)

    def __init__(self, edoves: "Edoves", config: "TemplateConfig"):
        self.config = config
        super().__init__(edoves, self.source_information.instance_identifier)

    @abstractmethod
    async def parse_raw_data(self, data: TData) -> BaseMedium:
        """将server端传入的原始数据封装"""
        raise NotImplementedError
