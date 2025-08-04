from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from io import StringIO
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, ClassVar, TypeVar
import warnings

from .model import Proxy, config_model_dump, config_model_validate
from .models.default import BasicConfModel as BasicConfModel
from .models.default import field as model_field
from .util import nest_dict_update

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

ENV_CONTEXT_PAT = re.compile(r"['\"]?\$\{\{\s?env\.(?P<name>[^}\s]+)\s?\}\}['\"]?")
T = TypeVar("T")


class BasicConfig(BasicConfModel):
    network: list[dict[str, Any]] = model_field(default_factory=list, description="Network configuration")
    ignore_self_message: bool = model_field(default=True, description="Ignore self message")
    skip_req_missing: bool = model_field(default=False, description="Skip Event Handler if requirement is missing")
    log_level: int | str = model_field(default="INFO", description="Log level for the application")
    log_ignores: list[str] = model_field(default_factory=list, description="Log ignores for the application")
    prefix: list[str] = model_field(default_factory=list, description="Command prefix for the application")
    cmd_count: int = model_field(default=4096, description="Command count limit for the application")
    external_dirs: list[str] = model_field(default_factory=list, description="External directories to look for plugins")


_loaders: dict[str, Callable[[str], dict]] = {}
_dumpers: dict[str, Callable[[Path, dict, int], None]] = {}


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=BasicConfig, init=False)
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    save_flag: bool = field(default=False)
    _basic_data: dict[str, Any] = field(default_factory=dict, init=False)

    instance: ClassVar[EntariConfig]

    @classmethod
    def loader(cls, path: Path):
        if not path.exists():
            return {}
        end = path.suffix.split(".")[-1]
        if end in _loaders:
            with path.open("r", encoding="utf-8") as f:
                text = f.read()
                text = ENV_CONTEXT_PAT.sub(lambda m: os.environ.get(m["name"], ""), text)
                return _loaders[end](text)

        raise ValueError(f"Unsupported file format: {path.suffix}")

    @classmethod
    def dumper(cls, path: Path, save_path: Path, data: dict, indent: int):
        if not path.exists():
            return
        origin = cls.loader(path)
        if "entari" in origin:
            nest_dict_update(origin["entari"], data)
        else:
            nest_dict_update(origin, data)
        end = save_path.suffix.split(".")[-1]
        if end in _dumpers:
            _dumpers[end](save_path, origin, indent)
            return
        raise ValueError(f"Unsupported file format: {save_path.suffix}")

    def __post_init__(self):
        self.__class__.instance = self
        self.reload()

    @property
    def data(self) -> dict[str, Any]:
        return self.loader(self.path)

    @property
    def prelude_plugin_names(self) -> list[str]:
        slots = [(name, self.plugin[name].get("$priority", 16)) for name in self.prelude_plugin if name in self.plugin]
        slots.sort(key=lambda x: x[1])
        return [name for name, _ in slots]

    @property
    def plugin_names(self) -> list[str]:
        slots = [
            (name, self.plugin[name].get("$priority", 16))
            for name in self.plugin
            if not name.startswith("~") and not name.startswith("$")
        ]
        slots.sort(key=lambda x: x[1])
        return [name for name, _ in slots]

    def reload(self):
        if self.save_flag:
            self.save_flag = False
            return False
        data = self.loader(self.path)
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
                    self.plugin[_path.stem] = self.loader(_path)
            else:
                self.plugin[path.stem] = self.loader(path)

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
        return True

    def dump(self, indent: int = 2):
        plugins = self.plugin.copy()
        if plugins[".commands"] == {}:
            plugins.pop(".commands")
        if self.prelude_plugin:
            plugins = {"$prelude": self.prelude_plugin, **plugins}
        if self.plugin_extra_files:
            for file in self.plugin_extra_files:
                path = Path(file)
                if path.is_file():
                    self.dumper(path, path, plugins.pop(path.stem), indent)
                else:
                    for _path in path.iterdir():
                        if _path.is_file():
                            self.dumper(_path, _path, plugins.pop(_path.stem), indent)
            plugins = {"$files": self.plugin_extra_files, **plugins}
        return {"basic": self._basic_data, "plugins": plugins}

    def save(self, path: str | os.PathLike[str] | None = None, indent: int = 2):
        self.save_flag = True
        self.dumper(self.path, Path(path or self.path), self.dump(indent), indent)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> EntariConfig:
        try:
            import dotenv

            dotenv.load_dotenv()
        except ImportError:
            dotenv = None  # noqa
            pass
        if not path:
            if "ENTARI_CONFIG_FILE" in os.environ:
                _path = Path(os.environ["ENTARI_CONFIG_FILE"])
            elif (Path.cwd() / ".entari.json").exists():
                _path = Path.cwd() / ".entari.json"
            else:
                _path = Path.cwd() / "entari.yml"
        else:
            _path = Path(path)
        if "ENTARI_CONFIG_EXTENSION" in os.environ:
            ext_mods = os.environ["ENTARI_CONFIG_EXTENSION"].split(";")
            for ext_mod in ext_mods:
                if not ext_mod:
                    continue
                ext_mod = ext_mod.replace("::", "arclet.entari.config.format.")
                try:
                    import_module(ext_mod)
                except ImportError as e:
                    warnings.warn(f"Failed to load config extension '{ext_mod}': {e}", ImportWarning)
        if not _path.exists():
            return cls(_path)
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")
        return cls(_path)

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


def register_loader(*ext: str):
    """Register a loader for a specific file extension."""

    def decorator(func: Callable[[str], dict]):
        for e in ext:
            _loaders[e] = func
        return func

    return decorator


def register_dumper(*ext: str):
    """Register a dumper for a specific file extension."""

    def decorator(func: Callable[[Path, dict, int], None]):
        for e in ext:
            _dumpers[e] = func
        return func

    return decorator


@register_loader("json")
def json_loader(text: str) -> dict:
    return json.loads(text)


@register_dumper("json")
def json_dumper(save_path: Path, origin: dict, indent: int):
    with save_path.open("w+", encoding="utf-8") as f:
        json.dump(origin, f, indent=indent, ensure_ascii=False)


@register_loader("yaml", "yml")
def yaml_loader(text: str) -> dict:
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml.load(StringIO(text))


@register_dumper("yaml", "yml")
def yaml_dumper(save_path: Path, origin: dict, indent: int):
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.indent(mapping=indent, sequence=indent + 2, offset=indent)
    with save_path.open("w+", encoding="utf-8") as f:
        yaml.dump(origin, f)
