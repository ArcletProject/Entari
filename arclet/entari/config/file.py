from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from importlib import import_module
from io import StringIO
import json
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar
import warnings

from tarina.tools import nest_dict_update, safe_eval

from .action import Proxy, config_model_dump, config_model_schema, config_model_validate
from .model import BasicConfig
from .util import GetattrDict

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

try:
    import dotenv as dotenv
except ImportError:
    dotenv = None
    pass

if TYPE_CHECKING:
    from ..plugin import Plugin

EXPR_CONTEXT_PAT = re.compile(r"['\"]?\$\{\{\s?(?P<expr>[^}\s]+)\s?\}\}['\"]?")
T = TypeVar("T")
T_M = TypeVar("T_M", bound=MutableMapping)


_loaders: dict[str, Callable[[str], dict]] = {}
_dumpers: dict[str, Callable[[dict, int, str | None], tuple[str, bool]]] = {}


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=BasicConfig, init=False)
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    save_flag: bool = field(default=False)
    env_vars: dict[str, str] = field(default_factory=dict)
    _origin_data: dict[str, Any] = field(init=False)
    _env_replaced: dict[str, dict[int, tuple[str, int]]] = field(default_factory=dict, init=False)

    instance: ClassVar["EntariConfig"]

    def loader(self, path: Path):
        if not path.exists():
            return {}
        end = path.suffix.split(".")[-1]
        if end in _loaders:
            ctx = {"env": GetattrDict(self.env_vars)}

            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):

                def handle(m: re.Match[str]):
                    expr = m.group("expr")
                    ans = safe_eval(expr, ctx)
                    self._env_replaced.setdefault(path.as_posix(), {})[i] = (line, len(ans.splitlines()))
                    return ans

                lines[i] = EXPR_CONTEXT_PAT.sub(handle, line)
            text = "".join(lines)
            return _loaders[end](text)

        raise ValueError(f"Unsupported file format: {path.suffix}")

    def dumper(self, path: Path, save_path: Path, data: dict, indent: int, apply_schema: bool):
        if not path.exists():
            return
        origin = self.loader(path)
        if "entari" in origin:
            origin["entari"] = data
        else:
            origin = data
        end = save_path.suffix.split(".")[-1]
        schema_file = None
        if apply_schema:
            schema_file = f"{save_path.stem}.schema.json"
        if end in _dumpers:
            ans, applied = _dumpers[end](origin, indent, schema_file)
            if path.as_posix() in self._env_replaced:
                lines = ans.splitlines(keepends=True)
                for i, (line, height) in self._env_replaced[path.as_posix()].items():
                    lines[i + applied] = line
                    for _ in range(height - 2):
                        lines.pop(i + applied + 1)
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
                if "$disable" not in value or isinstance(value["$disable"], bool):
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
                    if not _path.is_file() or _path.name.endswith(".schema.json"):
                        continue
                    self.plugin[_path.stem] = self.loader(_path)
            elif path.name.endswith(".schema.json"):
                self.plugin[path.stem] = self.loader(path)
        return True

    @staticmethod
    def _clean(value: T_M) -> T_M:
        value.pop("$path", None)
        value.pop("$static", None)
        return value

    def dump(self, indent: int = 2, apply_schema: bool = False) -> dict[str, Any]:
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
                if path.is_file() and not path.name.endswith(".schema.json"):
                    self.dumper(path, path, self._clean(self.plugin.pop(path.stem)), indent, apply_schema)
                else:
                    for _path in path.iterdir():
                        if _path.is_file() and not _path.name.endswith(".schema.json"):
                            self.dumper(_path, _path, self._clean(self.plugin.pop(_path.stem)), indent, apply_schema)
        for key in list(self.plugin.keys()):
            if key.startswith("$"):
                continue
            value = self.plugin.pop(key)
            if "$disable" in value and isinstance(value["$disable"], bool):
                key = f"~{key}" if value["$disable"] else key
                value.pop("$disable", None)
            if "$optional" in value:
                key = f"?{key}" if value["$optional"] else key
                value.pop("$optional", None)
            self.plugin[key] = self._clean(value)
        return self._origin_data

    def save(self, path: str | os.PathLike[str] | None = None, indent: int = 2, apply_schema: bool = False):
        self.save_flag = True
        self.dumper(self.path, Path(path or self.path), self.dump(indent, apply_schema), indent, apply_schema)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "EntariConfig":
        if dotenv:
            from .env import load_env_with_environment

            env_vars = load_env_with_environment()
        else:
            env_vars = dict(os.environ.items())
        if not path:
            if "ENTARI_CONFIG_FILE" in env_vars:
                _path = Path(env_vars["ENTARI_CONFIG_FILE"])
            elif (Path.cwd() / ".entari.json").exists():
                _path = Path.cwd() / ".entari.json"
            else:
                _path = Path.cwd() / "entari.yml"
        else:
            _path = Path(path)
        if "ENTARI_CONFIG_EXTENSION" in env_vars:
            ext_mods = env_vars["ENTARI_CONFIG_EXTENSION"].split(";")
            for ext_mod in ext_mods:
                if not ext_mod:
                    continue
                ext_mod = ext_mod.replace("::", "arclet.entari.config.format.")
                try:
                    import_module(ext_mod)
                except ImportError as e:
                    warnings.warn(f"Failed to load config extension '{ext_mod}': {e}", ImportWarning)
        if not _path.exists():
            return cls(_path, env_vars=env_vars)
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")
        return cls(_path, env_vars=env_vars)

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
        plugins_properties = {}
        # fmt: off
        plugin_meta_properties = {"$disable": {"type": "string", "description": "Expression for whether disable this plugin"}, "$prefix": {"type": "string", "description": "Plugin name prefix"}, "$priority": {"type": "integer", "description": "Plugin loading priority, lower value means higher priority (default: 16)"}, "$filter": {"type": "string", "description": "Plugin filter expression, which will be evaluated in the context of the plugin"}}  # noqa: E501
        # Build a mapping from plugin config key to plugin object for $files schema generation
        plugin_map: dict[str, "Plugin"] = {}  # noqa: UP037
        for plug in plugins:
            plugin_map[plug._config_key] = plug
            if plug.metadata is not None:
                if plug.metadata.config:
                    schema = config_model_schema(plug.metadata.config, ref_root=f"/properties/plugins/properties/{plug._config_key}/")  # noqa: E501
                    schema["properties"].update(plugin_meta_properties)
                    plugins_properties[plug._config_key] = schema
                else:
                    plugins_properties[plug._config_key] = {"type": "object", "description": f"{plug.metadata.description or plug.metadata.name}; no configuration required", "additionalProperties": True, "properties": plugin_meta_properties}  # noqa: E501
            else:
                plugins_properties[plug._config_key] = {"type": "object", "description": "No configuration required", "additionalProperties": True, "properties": plugin_meta_properties}  # noqa: E501
        schemas = {
            "basic": config_model_schema(BasicConfig, ref_root="/properties/basic/"), "plugins": {"type": "object", "description": "Plugin configurations", "properties": {"$prelude": {"type": "array", "items": {"type": "string", "description": "Plugin name"}, "description": "List of prelude plugins to load", "default": [], "uniqueItems": True}, "$files": {"type": "array", "items": {"type": "string", "description": "File path"}, "description": "List of configuration files to load", "default": [], "uniqueItems": True}, **plugins_properties}}, "adapters": {"type": "array", "description": "Adapter configurations", "items": {"type": "object", "description": "Adapter configuration", "properties": {"$path": {"type": "string", "description": "Adapter Module Path"}}, "required": ["$path"], "additionalProperties": True}}  # noqa: E501
        }
        with open(f"{self.path.stem}.schema.json", "w", encoding="utf-8") as f:
            json.dump({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": schemas, "additionalProperties": False, "required": ["basic"]}, f, indent=2, ensure_ascii=False)  # noqa: E501

        # Generate schema for each file in $files
        for file in self.plugin_extra_files:
            path = Path(file)
            if path.is_file() and not path.name.endswith(".schema.json"):
                self._generate_extra_file_schema(path, plugin_map, plugin_meta_properties)
            elif path.is_dir():
                for _path in path.iterdir():
                    if _path.is_file() and not _path.name.endswith(".schema.json"):
                        self._generate_extra_file_schema(_path, plugin_map, plugin_meta_properties)
        # fmt: on
        plugin_map.clear()

    def _generate_extra_file_schema(self, path: Path, plugin_map: dict[str, "Plugin"], plugin_meta_properties: dict):
        """Generate schema for an extra config file from $files."""
        plugin_key = path.stem
        schema_file = path.with_suffix(".schema.json")
        plugin_meta_properties = {
            **plugin_meta_properties,
            "$optional": {"type": "boolean", "description": "Whether this plugin is optional"},
        }  # noqa: E501

        # Check if we have a matching plugin with config
        if plugin_key in plugin_map:
            plug = plugin_map[plugin_key]
            if plug.metadata is not None and plug.metadata.config:
                plugin_schema = config_model_schema(plug.metadata.config, ref_root="/")
                plugin_schema["properties"].update(plugin_meta_properties)
            elif plug.metadata is not None:
                plugin_schema = {
                    "type": "object",
                    "description": f"{plug.metadata.description or plug.metadata.name}; no configuration required",
                    "additionalProperties": True,
                    "properties": plugin_meta_properties,
                }  # noqa: E501
            else:
                plugin_schema = {
                    "type": "object",
                    "description": "No configuration required",
                    "additionalProperties": True,
                    "properties": plugin_meta_properties,
                }  # noqa: E501
        else:
            # Plugin not found, generate a generic schema
            plugin_schema = {
                "type": "object",
                "description": f"Configuration for {plugin_key}",
                "additionalProperties": True,
                "properties": plugin_meta_properties,
            }  # noqa: E501

        with open(schema_file, "w", encoding="utf-8") as f:
            json.dump(
                {"$schema": "https://json-schema.org/draft/2020-12/schema", **plugin_schema},
                f,
                indent=2,
                ensure_ascii=False,
            )  # noqa: E501


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

    def decorator(func: Callable[[dict, int, str | None], tuple[str, bool]]):
        for e in ext:
            _dumpers[e] = func
        return func

    return decorator


@register_loader("json")
def json_loader(text: str) -> dict:
    return json.loads(text)


@register_dumper("json")
def json_dumper(origin: dict, indent: int, schema_file: str | None = None) -> tuple[str, bool]:
    schema_applied = False
    if schema_file and "$schema" not in origin:
        origin = {"$schema": f"{schema_file}", **origin}
        schema_applied = True
    return json.dumps(origin, indent=indent, ensure_ascii=False), schema_applied


@register_loader("yaml", "yml")
def yaml_loader(text: str) -> dict:
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml.load(StringIO(text))


@register_dumper("yaml", "yml")
def yaml_dumper(origin: dict, indent: int, schema_file: str | None = None) -> tuple[str, bool]:
    if YAML is None:
        raise RuntimeError("yaml is not installed. Please install with `arclet-entari[yaml]`")
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=indent, sequence=indent + 2, offset=indent)
    yaml.width = 4096
    sio = StringIO()
    yaml.dump(origin, sio)
    ans = sio.getvalue()
    schema_applied = False
    if schema_file:
        root = Path.cwd()
        if (root / ".vscode").exists():
            if not ans.startswith("# yaml-language-server: $schema="):
                ans = f"# yaml-language-server: $schema={schema_file}\n{ans}"
                schema_applied = True
        elif not ans.startswith("# $schema:"):
            ans = f"# $schema: {schema_file}\n{ans}"
            schema_applied = True
    return ans, schema_applied
