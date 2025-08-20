from dataclasses import dataclass, field
from importlib import import_module
from io import StringIO
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, ClassVar, TypeVar, Union
import warnings

from tarina.tools import nest_dict_update

from .model import Proxy, config_model_dump, config_model_validate
from .models.default import BasicConfModel as BasicConfModel
from .models.default import field as model_field

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

ENV_CONTEXT_PAT = re.compile(r"['\"]?\$\{\{\s?env\.(?P<name>[^}\s]+)\s?\}\}['\"]?")
T = TypeVar("T")


class LogSaveInfo(BasicConfModel):
    rotation: str = model_field(default="00:00", description="Log rotation time, e.g., '00:00' for daily rotation")
    compression: Union[str, None] = model_field(
        default=None, description="Compression format for log saving, e.g., 'zip'"
    )
    colorize: bool = model_field(default=True, description="Whether to colorize the log output")


class LogInfo(BasicConfModel):
    level: Union[int, str] = model_field(default="INFO", description="Log level for the application")
    ignores: list[str] = model_field(default_factory=list, description="Log ignores for the application")
    save: Union[LogSaveInfo, bool, None] = model_field(
        default=None,
        description="Log saving configuration, if None or False, logs will not be saved",
    )


class BasicConfig(BasicConfModel):
    network: list[dict[str, Any]] = model_field(default_factory=list, description="Network configuration")
    ignore_self_message: bool = model_field(default=True, description="Ignore self message")
    skip_req_missing: bool = model_field(default=False, description="Skip Event Handler if requirement is missing")
    log: LogInfo = model_field(default_factory=LogInfo, description="Log configuration")
    log_level: Union[int, str, None] = model_field(
        default=None, description="[Deprecated] Log level for the application"
    )
    log_ignores: Union[list[str], None] = model_field(
        default=None, description="[Deprecated] Log ignores for the application"
    )
    prefix: list[str] = model_field(default_factory=list, description="Command prefix for the application")
    cmd_count: int = model_field(default=4096, description="Command count limit for the application")
    external_dirs: list[str] = model_field(default_factory=list, description="External directories to look for plugins")

    def __post_init__(self):
        if self.log_level is not None:
            self.log.level = self.log_level
        if self.log_ignores is not None:
            self.log.ignores = self.log_ignores


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
    _origin_data: dict[str, Any] = field(init=False)

    instance: ClassVar["EntariConfig"]

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
            origin["entari"] = data
        else:
            origin = data
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
        return self._origin_data

    @property
    def prelude_plugin_names(self) -> list[str]:
        return [name for name in self.plugin_names if name in self.prelude_plugin]

    @property
    def plugin_names(self) -> list[str]:
        slots = [
            (name, self.plugin[name].get("$priority", 16))
            for name in self.plugin
            if not name.startswith("$") and not self.plugin[name].get("$optional", False)
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
        self._origin_data = data
        self.plugin = data.get("plugins", {})
        self.plugin_extra_files: list[str] = self.plugin.get("$files", [])  # type: ignore
        self.prelude_plugin = self.plugin.get("$prelude", [])  # type: ignore
        for key in list(self.plugin.keys()):
            if key.startswith("$"):
                continue
            value = self.plugin.pop(key)
            if key.startswith("~"):
                key = key[1:]
                value["$disable"] = True
            elif key.startswith("?"):
                key = key[1:]
                value["$optional"] = True
            self.plugin[key] = value
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
        return True

    def dump(self, indent: int = 2):
        basic = self._origin_data.get("basic", {})
        if "log" not in basic and ("log_level" in basic or "log_ignores" in basic):
            basic["log"] = {}
            if "log_level" in basic:
                basic["log"]["level"] = basic.pop("log_level")
            if "log_ignores" in basic:
                basic["log"]["ignores"] = basic.pop("log_ignores")

        def _clean(value: dict):
            return {k: v for k, v in value.items() if k not in {"$path", "$static"}}

        if self.plugin_extra_files:
            for file in self.plugin_extra_files:
                path = Path(file)
                if path.is_file():
                    self.dumper(path, path, _clean(self.plugin.pop(path.stem)), indent)
                else:
                    for _path in path.iterdir():
                        if _path.is_file():
                            self.dumper(_path, _path, _clean(self.plugin.pop(_path.stem)), indent)
        for key in list(self.plugin.keys()):
            if key.startswith("$"):
                continue
            value = self.plugin.pop(key)
            if "$disable" in value:
                key = f"~{key}" if value["$disable"] else key
                value.pop("$disable", None)
            if "$optional" in value:
                key = f"?{key}" if value["$optional"] else key
                value.pop("$optional", None)
            self.plugin[key] = _clean(value)
        return self._origin_data

    def save(self, path: Union[str, os.PathLike[str], None] = None, indent: int = 2):
        self.save_flag = True
        self.dumper(self.path, Path(path or self.path), self.dump(indent), indent)

    @classmethod
    def load(cls, path: Union[str, os.PathLike[str], None] = None) -> "EntariConfig":
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
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml.load(StringIO(text))


@register_dumper("yaml", "yml")
def yaml_dumper(save_path: Path, origin: dict, indent: int):
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=indent, sequence=indent + 2, offset=indent)
    with save_path.open("w+", encoding="utf-8") as f:
        yaml.dump(origin, f)
