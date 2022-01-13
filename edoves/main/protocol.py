from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Generic, Optional, Union, Type, TypeVar
from .medium import BaseMedium
from ..security import UNDEFINED, generate_identifier
from ..data_source_info import DataSourceInfo
from ..utilles import ModuleStatus
from .exceptions import ValidationFailed, DataMissing
from .typings import TConfig, TData
from .controller import Controller

TM = TypeVar("TM")


if TYPE_CHECKING:
    from . import Edoves
    from .module import BaseModule, MediumModule


class AbstractProtocol(metaclass=ABCMeta):
    edoves: "Edoves"
    medium: TData
    __identifier: int = UNDEFINED

    def __init__(self, edoves: "Edoves", identifier: Optional[Union[str, int]] = None):
        self.edoves = edoves
        if not identifier and self.__identifier == UNDEFINED:
            raise ValidationFailed
        if isinstance(identifier, int):
            self.__identifier = identifier
        else:
            self.__identifier = generate_identifier(identifier)

    @property
    def identifier(self):
        return self.__identifier

    def verify(self, other: Union[int, "BaseModule"]):
        if isinstance(other, int) and other != self.edoves.identifier:
            raise ValidationFailed
        if other.identifier != self.edoves.identifier:
            other.state = ModuleStatus.CLOSED
            raise ValidationFailed

    def get_medium(self, medium_type: Optional[Type[TM]]) -> Union[TM, TData]:
        if medium_type and not isinstance(self.medium, medium_type):
            return medium_type.create(self.edoves.self, Type[self.medium])(self.medium)
        return self.medium

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}>"
        )


class ModuleProtocol(AbstractProtocol):
    __controller: Controller[Type["MediumModule"], "MediumModule"]
    medium: BaseMedium

    def __init__(self, edoves: "Edoves", identifier: int):
        super().__init__(edoves, identifier)
        self.__controller = Controller(self.edoves)

    @property
    def modules(self) -> Controller[Type["MediumModule"], "MediumModule"]:
        return self.__controller


class NetworkProtocol(Generic[TConfig], AbstractProtocol):
    source_information: DataSourceInfo
    config: TConfig

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "source_information"):
            raise DataMissing
        return super(NetworkProtocol, cls).__new__(cls)

    def __init__(self, edoves: "Edoves", config: TConfig):
        self.config = config
        super().__init__(edoves, self.source_information.instance_identifier)

    @abstractmethod
    async def parse_raw_data(self, data: TData) -> BaseMedium:
        """将server端传入的原始数据封装"""
        raise NotImplementedError
