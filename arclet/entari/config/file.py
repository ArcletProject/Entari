from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from importlib import import_module
from io import StringIO
import json
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar
import warnings

from tarina.tools import nest_dict_update, safe_eval

from .model import Proxy, config_model_dump, config_model_schema, config_model_validate
from .models.default import BasicConfModel as BasicConfModel
from .models.default import field as model_field
from .util import GetattrDict

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

if TYPE_CHECKING:
    from ..plugin import Plugin

EXPR_CONTEXT_PAT = re.compile(r"['\"]?\$\{\{\s?(?P<expr>[^}\s]+)\s?\}\}['\"]?")
T = TypeVar("T")
T_M = TypeVar("T_M", bound=MutableMapping)


class WebsocketsInfo(BasicConfModel):
    """Satori Server WebSocket Configuration"""

    type: Literal["websocket", "websockets", "ws"]
    host: str = model_field(default="localhost", description="WebSocket server host")
    port: int = model_field(default=5140, description="WebSocket server port")
    path: str = model_field(default="", description="WebSocket server endpoint path")
    token: str | None = model_field(default=None, description="Authentication token for the WebSocket server")
    timeout: float | None = model_field(default=None, description="Connection timeout in seconds")


class WebhookInfo(BasicConfModel):
    """Satori Server Webhook Configuration"""

    type: Literal["webhook", "wh", "http"]
    host: str = model_field(default="127.0.0.1", description="Webhook self-server host")
    port: int = model_field(default=8080, description="Webhook self-server port")
    path: str = model_field(default="v1/events", description="Webhook self-server endpoint path")
    token: str | None = model_field(default=None, description="Authentication token for the webhook")
    server_host: str = model_field(default="localhost", description="Target server host")
    server_port: int = model_field(default=5140, description="Target server port")
    server_path: str = model_field(default="", description="Target server endpoint path")
    timeout: float | None = model_field(default=None, description="Connection timeout in seconds")


class LogSaveInfo(BasicConfModel):
    """Configuration for saving logs to a file"""

    rotation: str = model_field(default="00:00", description="Log rotation time, e.g., '00:00' for daily rotation")
    compression: str | None = model_field(default=None, description="Compression format for log saving, e.g., 'zip'")
    colorize: bool = model_field(default=True, description="Whether to colorize the log output")


class LogInfo(BasicConfModel):
    """Configuration for the application logs"""

    level: int | str = model_field(default="INFO", description="Log level for the application")
    ignores: list[str] = model_field(default_factory=list, description="Log ignores for the application")
    save: LogSaveInfo | bool | None = model_field(
        default=None,
        description="Log saving configuration, if None or False, logs will not be saved",
    )
    rich_error: bool = model_field(default=False, description="Whether enable rich traceback for exceptions")
    short_level: bool = model_field(default=False, description="Whether use short log level names")


class BasicConfig(BasicConfModel):
    """Basic configuration for the Entari application"""

    network: list[WebsocketsInfo | WebhookInfo] = model_field(default_factory=list, description="Network configuration")
    ignore_self_message: bool = model_field(default=True, description="Whether ignore self-send message event")
    skip_req_missing: bool = model_field(
        default=False, description="Whether skip Event Handler if requirement is missing"
    )
    log: LogInfo = model_field(default_factory=LogInfo, description="Log configuration")
    log_level: int | str | None = model_field(default=None, description="[Deprecated] Log level for the application")
    log_ignores: list[str] | None = model_field(
        default=None, description="[Deprecated] Log ignores for the application"
    )
    prefix: list[str] = model_field(default_factory=list, description="Command prefix for the application")
    cmd_count: int = model_field(default=4096, description="Command count limit for the application")
    external_dirs: list[str] = model_field(default_factory=list, description="External directories to look for plugins")
    schema: bool = model_field(
        default=False, description="Whether generate JSON schema for the configuration (after application start)"
    )

    def __post_init__(self):
        if self.log_level is not None:
            self.log.level = self.log_level
        if self.log_ignores is not None:
            self.log.ignores = self.log_ignores
        if self.prefix.count(""):
            self.prefix = [p for p in self.prefix if p]
            self.prefix.append("")


_loaders: dict[str, Callable[[str], dict]] = {}
_dumpers: dict[str, Callable[[dict, int], str]] = {}


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=BasicConfig, init=False)
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    save_flag: bool = field(default=False)
    _origin_data: dict[str, Any] = field(init=False)
    _env_replaced: dict[int, str] = field(default_factory=dict, init=False)

    instance: ClassVar["EntariConfig"]

    def loader(self, path: Path):
        if not path.exists():
            return {}
        end = path.suffix.split(".")[-1]
        if end in _loaders:
            ctx = {"env": GetattrDict(os.environ)}

            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):

                def handle(m: re.Match[str]):
                    self._env_replaced[i] = line
                    expr = m.group("expr")
                    return safe_eval(expr, ctx)

                lines[i] = EXPR_CONTEXT_PAT.sub(handle, line)
            text = "".join(lines)
            return _loaders[end](text)

        raise ValueError(f"Unsupported file format: {path.suffix}")

    def dumper(self, path: Path, save_path: Path, data: dict, indent: int):
        if not path.exists():
            return
        origin = self.loader(path)
        if "entari" in origin:
            origin["entari"] = data
        else:
            origin = data
        end = save_path.suffix.split(".")[-1]
        if end in _dumpers:
            ans = _dumpers[end](origin, indent)
            if self._env_replaced:
                lines = ans.splitlines(keepends=True)
                for i, line in self._env_replaced.items():
                    lines[i] = line
                ans = "".join(lines)
            with save_path.open("w", encoding="utf-8") as f:
                f.write(ans)
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

    @staticmethod
    def _clean(value: T_M) -> T_M:
        value.pop("$path", None)
        value.pop("$static", None)
        return value

    def dump(self, indent: int = 2):
        basic = self._origin_data.get("basic", {})
        if "log" not in basic and ("log_level" in basic or "log_ignores" in basic):
            basic["log"] = {}
            if "log_level" in basic:
                basic["log"]["level"] = basic.pop("log_level")
            if "log_ignores" in basic:
                basic["log"]["ignores"] = basic.pop("log_ignores")

        if self.plugin_extra_files:
            for file in self.plugin_extra_files:
                path = Path(file)
                if path.is_file():
                    self.dumper(path, path, self._clean(self.plugin.pop(path.stem)), indent)
                else:
                    for _path in path.iterdir():
                        if _path.is_file():
                            self.dumper(_path, _path, self._clean(self.plugin.pop(_path.stem)), indent)
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
            self.plugin[key] = self._clean(value)
        return self._origin_data

    def save(self, path: str | os.PathLike[str] | None = None, indent: int = 2):
        self.save_flag = True
        self.dumper(self.path, Path(path or self.path), self.dump(indent), indent)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "EntariConfig":
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

    def generate_schema(self, plugins: list["Plugin"]):
        # fmt: off
        schemas = {
            "basic": config_model_schema(BasicConfig, ref_root="/properties/basic/"),
            "plugins": {
                "type": "object", "description": "Plugin configurations", "properties": {"$prelude": {"type": "array", "items": {"type": "string", "description": "Plugin name"}, "description": "List of prelude plugins to load", "default": [], "uniqueItems": True}, "$files": {"type": "array", "items": {"type": "string", "description": "File path"}, "description": "List of configuration files to load", "default": [], "uniqueItems": True}, **{plug._config_key: ((config_model_schema(plug.metadata.config, ref_root=f"/properties/plugins/properties/{plug._config_key}/") if plug.metadata.config is not None else {"type": "object", "description": f"{plug.metadata.description or plug.metadata.name}; no configuration required", "additionalProperties": True}) if plug.metadata else {"type": "object", "description": "No configuration required", "additionalProperties": True}) for plug in plugins}}  # noqa: E501
            }
        }
        with open(f"{self.path.stem}.schema.json", "w", encoding="utf-8") as f:
            json.dump({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": schemas, "additionalProperties": False, "required": ["basic"]}, f, indent=2, ensure_ascii=False)  # noqa: E501
        # fmt: on


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

    def decorator(func: Callable[[dict, int], str]):
        for e in ext:
            _dumpers[e] = func
        return func

    return decorator


@register_loader("json")
def json_loader(text: str) -> dict:
    return json.loads(text)


@register_dumper("json")
def json_dumper(origin: dict, indent: int):
    return json.dumps(origin, indent=indent, ensure_ascii=False)


@register_loader("yaml", "yml")
def yaml_loader(text: str) -> dict:
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml.load(StringIO(text))


@register_dumper("yaml", "yml")
def yaml_dumper(origin: dict, indent: int):
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=indent, sequence=indent + 2, offset=indent)
    sio = StringIO()
    yaml.dump(origin, sio)
    return sio.getvalue()
