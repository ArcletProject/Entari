from dataclasses import dataclass
from typing import Any, Optional

from arclet.letoderea import make_event


@dataclass
@make_event(name="entari.event/config_reload")
class ConfigReload:
    scope: str
    key: str
    value: Any
    old: Optional[Any] = None

    __result_type__: type[bool] = bool
