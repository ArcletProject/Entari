from typing import Any, Literal, Optional

from arclet.letoderea import make_event


@make_event(name="entari.event/config/reload")
class ConfigReload:
    scope: Literal["basic", "plugin"]
    key: str
    value: Any
    old: Optional[Any] = None

    def __post_init__(self):
        self.key = self.key.lstrip("~")

    __result_type__: type[bool] = bool
