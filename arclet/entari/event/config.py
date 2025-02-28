from dataclasses import dataclass
from typing import Any, Optional, TypeVar, overload

from arclet.letoderea import make_event

from ..config import config_model_validate

_C = TypeVar("_C")


@dataclass
@make_event(name="entari.event/config/reload")
class ConfigReload:
    scope: str
    key: str
    value: Any
    old: Optional[Any] = None

    __result_type__: type[bool] = bool

    @overload
    def plugin_config(self) -> dict[str, Any]: ...

    @overload
    def plugin_config(self, model_type: type[_C]) -> _C: ...

    def plugin_config(self, model_type: Optional[type[_C]] = None):
        if self.scope != "plugin":
            raise ValueError("not a plugin config")
        if model_type:
            return config_model_validate(model_type, self.value)
        return self.value
