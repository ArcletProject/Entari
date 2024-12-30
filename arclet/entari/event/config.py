from dataclasses import dataclass
from typing import Any, Optional, overload

from arclet.letoderea import make_event

from ..config import C, config_model_validate


@dataclass
@make_event(name="entari.event/config_reload")
class ConfigReload:
    scope: str
    key: str
    value: Any
    old: Optional[Any] = None

    __result_type__: type[bool] = bool

    @overload
    def plugin_config(self) -> dict[str, Any]: ...

    @overload
    def plugin_config(self, model_type: type[C]) -> C: ...

    def plugin_config(self, model_type: Optional[type[C]] = None):
        if self.scope != "plugin":
            raise ValueError("not a plugin config")
        if model_type:
            return config_model_validate(model_type, self.value)
        return self.value
