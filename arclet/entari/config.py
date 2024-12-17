from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Callable, ClassVar, TypedDict
import warnings


class BasicConfig(TypedDict, total=False):
    network: list[dict[str, Any]]
    ignore_self_message: bool
    log_level: int | str
    prefix: list[str]


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=dict, init=False)  # type: ignore
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    updater: Callable[[EntariConfig], None]

    instance: ClassVar[EntariConfig]

    def __post_init__(self):
        self.__class__.instance = self
        self.reload()

    def reload(self):
        self.updater(self)
        self.plugin.setdefault(".commands", {})
        self.prelude_plugin = self.plugin.pop("$prelude", [])  # type: ignore
        disabled = []
        for k, v in self.plugin.items():
            if v is True:
                self.plugin[k] = {}
                warnings.warn(
                    f"`True` usage in plugin '{k}' config is deprecated, use empty dict instead", DeprecationWarning
                )
            elif v is False:
                disabled.append(k)
        for k in disabled:
            self.plugin[f"~{k}"] = self.plugin.pop(k)
            warnings.warn(
                f"`False` usage in plugin '{k}' config is deprecated, use `~` prefix instead", DeprecationWarning
            )

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> EntariConfig:
        if path is None:
            try:
                import yaml

                _path = Path.cwd() / "entari.yml"
            except ImportError:
                _path = Path.cwd() / ".entari.json"
        else:
            _path = Path(path)
        if not _path.exists():
            return cls(_path, lambda _: None)
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")
        if _path.suffix.startswith(".json"):

            def _updater(self: EntariConfig):
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "entari" in data:
                        data = data["entari"]
                    self.basic = data.get("basic", {})
                    self.plugin = data.get("plugins", {})

            obj = cls(_path, _updater)
            cls.instance = obj
            return obj
        if _path.suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError:
                raise RuntimeError("yaml is not installed")

            def _updater(self: EntariConfig):
                with self.path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if "entari" in data:
                        data = data["entari"]
                    self.basic = data.get("basic", {})
                    self.plugin = data.get("plugins", {})

            return cls(_path, _updater)
        raise NotImplementedError(f"unsupported config file format: {_path.suffix}")


load_config = EntariConfig.load
