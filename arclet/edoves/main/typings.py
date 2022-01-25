from datetime import timedelta, datetime
from typing import TypeVar, TYPE_CHECKING, Union, List, Dict

if TYPE_CHECKING:
    from .config import TemplateConfig
    from .protocol import NetworkProtocol, ModuleProtocol, MonomerProtocol

TMeta = Union[str, bool, int, float, datetime, timedelta, None, List, Dict]
TData = Union[TMeta, List[TMeta], Dict[str, TMeta]]

TProtocol = TypeVar("TProtocol")
TNProtocol = TypeVar("TNProtocol", bound="NetworkProtocol")
TMProtocol = TypeVar("TMProtocol", bound="ModuleProtocol")
TMonoProtocol = TypeVar("TMonoProtocol", bound="MonomerProtocol")

TConfig = TypeVar("TConfig", bound="TemplateConfig")


