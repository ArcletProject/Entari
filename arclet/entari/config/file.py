from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, ClassVar, TypedDict
import warnings

from .util import nest_dict_update

ENV_CONTEXT_PAT = re.compile(r"\$\{\{\s?env\.(?P<name>[^}\s]+)\s?\}\}")


class BasicConfig(TypedDict, total=False):
    network: list[dict[str, Any]]
    ignore_self_message: bool
    skip_req_missing: bool
    log_level: int | str
    prefix: list[str]
    cmd_count: int
    external_dirs: list[str]


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=dict, init=False)  # type: ignore
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    loader: Callable[[EntariConfig], dict[str, Any]]

    instance: ClassVar[EntariConfig]

    def __post_init__(self):
        self.__class__.instance = self
        self.reload()

    @staticmethod
    def _load_plugin(path: Path):
        if path.suffix.startswith(".json"):
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        if path.suffix in (".yaml", ".yml"):
            try:
                from ruamel.yaml import YAML
            except ImportError:
                raise RuntimeError("yaml is not installed")

            yaml = YAML(typ="safe")
            yaml.indent(mapping=2, sequence=4, offset=2)

            with path.open("r", encoding="utf-8") as f:
                return yaml.load(f)
        raise NotImplementedError(f"unsupported plugin config file format: {path!s}")

    def reload(self):
        data = self.loader(self)
        if "entari" in data:
            data = data["entari"]
        self.basic = data.get("basic", {})
        self.plugin = data.get("plugins", {})
        self.plugin_extra_files: list[str] = self.plugin.pop("$files", [])  # type: ignore
        for file in self.plugin_extra_files:
            path = Path(file)
            if not path.exists():
                raise FileNotFoundError(file)
            if path.is_dir():
                for _path in path.iterdir():
                    if not _path.is_file():
                        continue
                    self.plugin[_path.stem] = self._load_plugin(_path)
            else:
                self.plugin[path.stem] = self._load_plugin(path)

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

    def dump(self):
        plugins = self.plugin.copy()
        if plugins[".commands"] == {}:
            plugins.pop(".commands")
        if self.prelude_plugin:
            plugins = {"$prelude": self.prelude_plugin, **plugins}
        if self.plugin_extra_files:
            for file in self.plugin_extra_files:
                path = Path(file)
                if path.is_file():
                    plugins.pop(path.stem)
                else:
                    for _path in path.iterdir():
                        if _path.is_file():
                            plugins.pop(_path.stem)
            plugins = {"$files": self.plugin_extra_files, **plugins}
        return {"basic": self.basic, "plugins": plugins}

    def save_json(self, path: str | os.PathLike[str], indent: int = 2):
        origin = self.loader(self)
        if "entari" in origin:
            origin["entari"] = self.dump()
        else:
            origin = self.dump()
        with Path(path).open("w+", encoding="utf-8") as f1:
            json.dump(origin, f1, indent=indent, ensure_ascii=False)

    def save_yaml(self, path: str | os.PathLike[str], indent: int = 2):
        origin = self.loader(self)
        if "entari" in origin:
            nest_dict_update(origin["entari"], self.dump())
        else:
            nest_dict_update(origin, self.dump())

        try:
            from ruamel.yaml import YAML
        except ImportError:
            raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]")

        yaml = YAML()
        yaml.indent(mapping=indent, sequence=indent + 2, offset=indent)
        with Path(path).open("w+", encoding="utf-8") as f1:
            yaml.dump(origin, f1)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> EntariConfig:
        try:
            import dotenv

            dotenv.load_dotenv()
        except ImportError:
            dotenv = None  # noqa
            pass
        if path is None:
            if "ENTARI_CONFIG_FILE" in os.environ:
                _path = Path(os.environ["ENTARI_CONFIG_FILE"])
            elif (Path.cwd() / ".entari.json").exists():
                _path = Path.cwd() / ".entari.json"
            else:
                _path = Path.cwd() / "entari.yml"
        else:
            _path = Path(path)
        if not _path.exists():
            return cls(_path, lambda _: {})
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")

        if _path.suffix.startswith(".json"):

            def _json_loader(self: EntariConfig):
                with self.path.open("r", encoding="utf-8") as f:
                    return json.load(f)

            obj = cls(_path, _json_loader)
            cls.instance = obj
            return obj
        if _path.suffix in (".yaml", ".yml"):
            try:
                from ruamel.yaml import YAML
            except ImportError:
                raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")

            def _yaml_loader(self: EntariConfig):
                yaml = YAML()
                yaml.indent(mapping=2, sequence=4, offset=2)

                with self.path.open("r", encoding="utf-8") as f:
                    text = f.read()
                    text = ENV_CONTEXT_PAT.sub(lambda m: os.environ.get(m["name"], ""), text)
                    return yaml.load(text)

            return cls(_path, _yaml_loader)
        raise NotImplementedError(f"unsupported config file format: {_path!s}")


load_config = EntariConfig.load
