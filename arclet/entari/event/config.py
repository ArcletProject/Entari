from pathlib import Path
from typing import Any, Literal

from arclet.letoderea import Result, make_event

from ..config.model import ApplyReport


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


@make_event(name="entari.event/config_modify")
class ConfigModify:
    path: Path
    source: str = "unknown"

    def check_result(self, value) -> Result[ApplyReport] | None:
        if isinstance(value, ApplyReport):
            return Result(value)
        if isinstance(value, bool):
            return Result(ApplyReport(ok=value, applied=value))
