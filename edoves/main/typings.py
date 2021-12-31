from datetime import timedelta, datetime
from typing import TypeVar, TYPE_CHECKING, Union, List, Dict

if TYPE_CHECKING:
    from .protocol import NetworkProtocol, ModuleProtocol, AbstractProtocol

TMeta = Union[str, bool, int, float, datetime, timedelta, None]
TData = Union[TMeta, List[TMeta], Dict[str, TMeta]]

TProtocol = TypeVar("TProtocol")
TNProtocol = TypeVar("TNProtocol", bound="NetworkProtocol")
TMProtocol = TypeVar("TMProtocol", bound="ModuleProtocol")

TConfig = TypeVar("TConfig")


