from datetime import timedelta, datetime
from typing import TypeVar, TYPE_CHECKING, Union, List, Dict

if TYPE_CHECKING:
    from .config import TemplateConfig
    from .protocol import AbstractProtocol

TMeta = Union[str, bool, int, float, datetime, timedelta, None, List, Dict]
TData = Union[TMeta, List[TMeta], Dict[str, TMeta]]

TProtocol = TypeVar("TProtocol", bound="AbstractProtocol")
TConfig = TypeVar("TConfig", bound="TemplateConfig")


