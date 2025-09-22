from typing import Any, Literal

from arclet.letoderea import Result, make_event


@make_event(name="entari.event/config_reload")
class ConfigReload:
    scope: Literal["basic", "plugin"]
    key: str
    value: Any
    old: Any = None

    def __post_init__(self):
        self.key = self.key.lstrip("~")

    def check_result(self, value) -> Result[bool] | None:
        if isinstance(value, bool):
            return Result(value)
