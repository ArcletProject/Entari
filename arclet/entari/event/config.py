from dataclasses import dataclass
from typing import Any, Optional

from arclet.letoderea import es

from .base import BasedEvent


@dataclass
class ConfigReload(BasedEvent):
    scope: str
    key: str
    value: Any
    old: Optional[Any] = None

    __publisher__ = "entari.event/config_reload"
    __result_type__: type[bool] = bool


pub = es.define(ConfigReload.__publisher__, ConfigReload)
