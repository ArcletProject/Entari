from abc import ABCMeta
from typing import TYPE_CHECKING, Generic, Optional, Union
from .medium import BaseMedium
from ..security import UNDEFINED, generate_identifier
from ..data_source_info import DataSourceInfo
from ..utilles import ModuleStatus
from .exceptions import ValidationFailed, DataMissing
from .typings import TConfig, TData


if TYPE_CHECKING:
    from . import Edoves
    from .module import BaseModule


class AbstractProtocol(metaclass=ABCMeta):
    client: "Edoves"
    medium: TData
    __identifier: int = UNDEFINED

    def __init__(self, client: "Edoves", identifier: Optional[Union[str, int]] = None):
        self.client = client
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
        if isinstance(other, int) and other != self.client.identifier:
            raise ValidationFailed
        if other.identifier != self.client.identifier:
            other.state = ModuleStatus.CLOSED
            raise ValidationFailed

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}>"
        )


class ModuleProtocol(AbstractProtocol):
    medium: BaseMedium


class NetworkProtocol(Generic[TConfig], AbstractProtocol):
    source_information: DataSourceInfo
    config: TConfig

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "source_information"):
            raise DataMissing
        return super(NetworkProtocol, cls).__new__(cls)

    def __init__(self, client: "Edoves", config: TConfig):
        self.config = config
        super().__init__(client, self.source_information.instance_identifier)
