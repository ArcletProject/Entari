from typing import Any, Literal, Optional, TypeVar, overload

from arclet.letoderea import make_event

from ..config import config_model_validate

_C = TypeVar("_C")


@make_event(name="entari.event/config/reload")
class ConfigReload:
    scope: Literal["basic", "plugin"]
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
