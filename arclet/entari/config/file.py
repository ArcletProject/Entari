from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, ClassVar, TypeVar
import warnings

from .model import BasicConfModel, Proxy, config_model_dump, config_model_validate
from .util import nest_dict_update

ENV_CONTEXT_PAT = re.compile(r"\$\{\{\s?env\.(?P<name>[^}\s]+)\s?\}\}")
T = TypeVar("T")


class BasicConfig(BasicConfModel):
    network: list[dict[str, Any]] = field(default_factory=list)
    ignore_self_message: bool = True
    skip_req_missing: bool = False
    log_level: int | str = "INFO"
    prefix: list[str] = field(default_factory=list)
    cmd_count: int = 4096
    external_dirs: list[str] = field(default_factory=list)


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=BasicConfig, init=False)
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    loader: Callable[[EntariConfig], dict[str, Any]]
    dumper: Callable[[EntariConfig, Path, int], None]
    save_flag: bool = field(default=False)
    _basic_data: dict[str, Any] = field(default_factory=dict, init=False)

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
        self.basic = config_model_validate(BasicConfig, data.get("basic", {}))
        self._basic_data = data.get("basic", {})
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
        return {"basic": self._basic_data, "plugins": plugins}

    def save(self, path: str | os.PathLike[str] | None = None, indent: int = 2):
        self.save_flag = True
        self.dumper(self, Path(path or self.path), indent)

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
            return cls(_path, lambda _: {}, lambda _, __, ___: None)
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")

        if _path.suffix.startswith(".json"):

            def _json_loader(self: EntariConfig):
                with self.path.open("r", encoding="utf-8") as f:
                    return json.load(f)

            def _json_dumper(self: EntariConfig, pth: Path, indent: int):
                origin = self.loader(self)
                if "entari" in origin:
                    origin["entari"] = self.dump()
                else:
                    origin = self.dump()
                with pth.open("w+", encoding="utf-8") as f1:
                    json.dump(origin, f1, indent=indent, ensure_ascii=False)

            return cls(_path, _json_loader, _json_dumper)
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

            def _yaml_dumper(self: EntariConfig, pth: Path, indent: int):
                origin = self.loader(self)
                if "entari" in origin:
                    nest_dict_update(origin["entari"], self.dump())
                else:
                    nest_dict_update(origin, self.dump())

                yaml = YAML()
                yaml.indent(mapping=indent, sequence=indent + 2, offset=indent)
                with pth.open("w+", encoding="utf-8") as f1:
                    yaml.dump(origin, f1)

            return cls(_path, _yaml_loader, _yaml_dumper)
        raise NotImplementedError(f"unsupported config file format: {_path!s}")

    def bind(self, plugin: str, obj: T) -> T:
        """
        Bind the plugin object to the config, allowing the config to be updated when the object changes.
        """
        if plugin not in self.plugin:
            raise KeyError(f"Plugin Config {plugin} not found in config")

        def updater(target):
            nest_dict_update(self.plugin[plugin], config_model_dump(target))
            self.save()

        ans = Proxy(obj, lambda target=obj: updater(target))
        return ans  # type: ignore


load_config = EntariConfig.load
