from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Callable, ClassVar


@dataclass
class Config:
    path: Path
    basic: dict = field(default_factory=dict, init=False)
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    updater: Callable[[Config], None]

    instance: ClassVar[Config]

    def __post_init__(self):
        self.__class__.instance = self
        self.updater(self)

    def reload(self):
        self.updater(self)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> Config:
        if path is None:
            _path = Path.cwd() / ".entari.json"
        else:
            _path = Path(path)
        if not _path.exists():
            return cls(_path, lambda _: None)
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")
        if _path.suffix.startswith(".json"):

            def _updater(self: Config):
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
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

            def _updater(self: Config):
                with self.path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    self.basic = data.get("basic", {})
                    self.plugin = data.get("plugins", {})

            return cls(_path, _updater)
        raise NotImplementedError(f"unsupported config file format: {_path.suffix}")


load_config = Config.load
