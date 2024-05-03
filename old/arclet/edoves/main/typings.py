from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, TypeVar, Union

if TYPE_CHECKING:
    from .config import TemplateConfig
    from .protocol import AbstractProtocol

TMeta = Union[str, bool, int, float, datetime, timedelta, None, List, Dict]
TData = Union[TMeta, List[TMeta], Dict[str, TMeta]]

TProtocol = TypeVar("TProtocol", bound="AbstractProtocol")
TConfig = TypeVar("TConfig", bound="TemplateConfig")
