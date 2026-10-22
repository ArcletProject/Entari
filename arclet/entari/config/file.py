import json
import os
import re
import warnings
from collections import defaultdict
from collections.abc import Callable, MutableMapping
from copy import deepcopy
from dataclasses import dataclass, field
from importlib import import_module
from io import StringIO
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from tarina.tools import nest_dict_update, safe_eval

from .action import Proxy, config_model_dump, config_model_schema, config_model_validate
from .model import BasicConfig
from .schema import apply_schema_fragments
from .schema.plugin import PLUGIN_META_PROPERTIES_EXTRA, plugin_config_schema
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

EXPR_CONTEXT_PAT = re.compile(r"\$\{\{\s?(?P<expr>[^}]+)\s?\}\}")
T = TypeVar("T")
T_M = TypeVar("T_M", bound=MutableMapping)


_loaders: dict[str, Callable[[str], dict]] = {}
_dumpers: dict[str, Callable[[dict, int, str | None], tuple[str, bool]]] = {}


@dataclass(unsafe_hash=True, slots=True)
class _EnvReplaced:
    parts: tuple[str, ...]
    target: str
    source: str


def _iter_values(obj: dict[str, Any], transform: Callable[[Any, str, list[str]], Any], history: list[str]):
    for k, v in obj.items():
        obj[k] = transform(v, k, history + [k])
    return obj


def _interpolate(source: str, context: dict[str, Any], records: set[_EnvReplaced], history: list[str]):
    def handle(m: re.Match[str]):
        expr = m.group("expr")
        expr, sep, default = expr.partition(":-")
        expr = expr.strip()
        default = default.strip()
        ans = safe_eval(expr, context)

        if ans is None:
            if not sep:
                return m.group()
            rendered = default
        else:
            rendered = str(ans)
        records.add(_EnvReplaced(tuple(history), rendered, m.group()))
        return rendered

    return re.sub(EXPR_CONTEXT_PAT, handle, source)


def _resolve_record_key(node: Any, part: str | int) -> tuple[str | int, Any]:
    try:
        return part, node[part]
    except KeyError:
        for prefix in ("~", "?"):
            alias = f"{prefix}{part}"
            if alias in node:
                return alias, node[alias]
        raise


@dataclass
class EntariConfig:
    path: Path
    basic: BasicConfig = field(default_factory=BasicConfig, init=False)
    plugin: dict[str, dict] = field(default_factory=dict, init=False)
    plugin_prefixes: dict[str, list[str]] = field(default_factory=dict, init=False)
    prelude_plugin: list[str] = field(default_factory=list, init=False)
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    save_flag: bool = field(default=False)
    register_instance: bool = field(default=True, repr=False)
    env_vars: dict[str, str] = field(default_factory=dict)
    _plugin_names: dict[str, list[str]] = field(default_factory=dict, init=False)
    _origin_data: dict[str, Any] = field(default_factory=dict, init=False)
    _records: dict[str, set[_EnvReplaced]] = field(default_factory=dict, init=False)
    _root_plugin_keys: set[str] = field(default_factory=set, init=False)
    _extra_stems: dict[str, set[str]] = field(default_factory=dict, init=False)

    instance: ClassVar["EntariConfig"]
    _inited: ClassVar[bool] = False

    def __post_init__(self):
        if self.register_instance:
            self.__class__.instance = self
            self.__class__._inited = True
        self.reload()

    def loader(self, path: Path, register: bool = True) -> dict[str, Any]:
        if not path.exists():
            return {}
        end = path.suffix.split(".")[-1]
        if end in _loaders:
            ctx = {"env": GetattrDict(self.env_vars)}

            with path.open("r", encoding="utf-8") as f:
                data = _loaders[end](f.read())

            records: set[_EnvReplaced] = set()
            if register:
                self._records[path.resolve().as_posix()] = records

            def _transform(value, key, history):
                if isinstance(value, str):
                    return _interpolate(value, ctx, records, history)
                elif isinstance(value, dict):
                    return _iter_values(value, _transform, history)
                elif isinstance(value, list):
                    for i, v in enumerate(value):
                        value[i] = _transform(v, "", history + [f"${i}"])
                return value

            data = _iter_values(data, _transform, [])
            return data

        raise ValueError(f"Unsupported file format: {path.suffix}")

    def _load_root(self) -> dict[str, Any]:
        data = self.loader(self.path)
        if "entari" in data:
            data = data["entari"]
        return data

    def dumper(self, path: Path, save_path: Path, data: dict, indent: int, apply_schema: bool):
        if not path.exists():
            return
        origin = self.loader(path, register=False)
        if "entari" in origin:
            origin["entari"] = data
        else:
            origin = data
        origin = deepcopy(origin)
        end = save_path.suffix.split(".")[-1]
        schema_file = None
        if apply_schema:
            schema_file = f"{save_path.stem}.schema.json"

        if end in _dumpers:
            for record in list(self._records.get(path.resolve().as_posix(), ())):
                parts = [
                    int(part[1:]) if part.startswith("$") and part[1:].isdigit() else part for part in record.parts
                ]
                try:
                    node: dict = origin
                    for part in parts[:-1]:
                        _, node = _resolve_record_key(node, part)
                    key, value = _resolve_record_key(node, parts[-1])
                    if isinstance(value, str) and record.target and record.target in value:
                        node[key] = value.replace(record.target, record.source)
                except (KeyError, IndexError, TypeError):
                    continue
            ans, applied = _dumpers[end](origin, indent, schema_file)
            with save_path.open("w", encoding="utf-8") as f:
                f.write(ans)
            self.refresh_records(save_path)
            return
        raise ValueError(f"Unsupported file format: {save_path.suffix}")

    def refresh_records(self, path: Path):
        if not path.exists():
            return
        # register=True 会重建该文件的记录；只更新 _records，不替换 _origin_data
        self.loader(path)

    def remap_records(self, path: Path, mapper: Callable[[tuple[str, ...]], tuple[str | int, ...] | None]):
        if not path.exists():
            return
        key = path.resolve().as_posix()
        records = self._records.get(key, set())
        new_records: set[_EnvReplaced] = set()
        for record in records:
            new_parts = mapper(record.parts)
            if new_parts is not None:
                new_records.add(
                    _EnvReplaced(
                        tuple(f"${p}" if isinstance(p, int) else p for p in new_parts), record.target, record.source
                    )
                )
        self._records[key] = new_records

    @property
    def data(self) -> dict[str, Any]:
        return self._origin_data

    @property
    def prelude_plugin_names(self) -> list[str]:
        return [
            name
            for key, names in self._plugin_names.items()
            for name in names
            if key in self.prelude_plugin or name in self.prelude_plugin
        ]

    @property
    def plugin_names(self) -> list[str]:
        return list(chain.from_iterable(self._plugin_names.values()))

    def _resolve_extra(self, entry: str) -> Path:
        path = Path(entry)
        if not path.is_absolute():
            path = self.path.parent / path
        return path.resolve()

    def _iter_extra_files(self, entry: str) -> list[Path]:
        path = self._resolve_extra(entry)
        if path.is_dir():
            return sorted(
                file.resolve() for file in path.iterdir() if file.is_file() and not file.name.endswith(".schema.json")
            )
        if path.name.endswith(".schema.json"):
            return []
        if not path.exists():
            raise FileNotFoundError(entry)
        return [path]

    def _find_extra_entry(self, target: Path) -> str | None:
        for entry in self.plugin.get("$files", []):
            base = self._resolve_extra(entry)
            if target == base:
                return entry
            if base.is_dir() and target.parent == base:
                return entry
        return None

    def _reload_plugins(self, *, load_files: bool = True):
        self.plugin_extra_files = self.plugin.get("$files", [])  # type: ignore
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

        extra_plugins: dict[str, list[str]] = {}
        for entry in self.plugin_extra_files:
            if load_files:
                stems: set[str] = set()
                for file in self._iter_extra_files(entry):
                    stem = file.stem
                    self.plugin[stem] = self.loader(file)
                    stems.add(stem)
                for name in self._extra_stems.get(entry, set()) - stems:
                    self.plugin.pop(name, None)
                self._extra_stems[entry] = stems
            else:
                stems = {s for s in self._extra_stems.get(entry, set()) if s in self.plugin}
            extra_plugins[entry] = sorted(stems)

        plugin_prefixes = {}
        for item in self.plugin.get("$prefix", []):  # type: ignore
            if "key" not in item or "plugins" not in item:
                continue
            _prefixes = plugin_prefixes.setdefault(item["key"], [])
            if isinstance(item["plugins"], list):
                _prefixes.extend(item["plugins"])
            elif isinstance(item["plugins"], str) and item["plugins"] in extra_plugins:
                _prefixes.extend(extra_plugins[item["plugins"]])
        inverted = defaultdict(list)
        for key, plugs in plugin_prefixes.items():
            for plug in plugs:
                inverted[plug].append(key)
        self.plugin_prefixes = dict(inverted)

        slots = [
            (name, self.plugin[name].get("$priority", 16))
            for name in self.plugin
            if not name.startswith("$") and not self.plugin[name].get("$optional", False)
        ]
        slots.sort(key=lambda x: x[1])
        ans: defaultdict[str, list[str]] = defaultdict(list)
        for name, _ in slots:
            if (prefixes := self.plugin_prefixes.get(name)) is not None:
                ans[name].extend((f"{prefix}{name}" if prefix else name) for prefix in prefixes)
            elif name.count(".") or name.startswith("::") or name.startswith("entari_plugin_"):
                ans[name].append(name)
            else:
                ans[name].append(f"entari_plugin_{name}")
        self._plugin_names = dict(ans)

    def _restore_records(
        self,
        snapshot: dict[str, set[_EnvReplaced] | None],
        *,
        replace_all: bool = False,
    ) -> None:
        if replace_all:
            # 整根 reload 可能解析了快照里没有的新 $files，先把整个 dict 清掉
            self._records = {}
        for key, records in snapshot.items():
            if records is None:
                self._records.pop(key, None)
            else:
                self._records[key] = set(records)

    def reload(self, force: bool = False) -> bool:
        if self.save_flag:
            self.save_flag = False
            if not force:
                return False
        snapshot = (
            self.basic,
            self._origin_data,
            self.plugin,
            self.plugin_extra_files,
            self.prelude_plugin,
            self.plugin_prefixes,
            self._plugin_names,
            self._root_plugin_keys,
            self._extra_stems,
            {key: set(records) for key, records in self._records.items()},
        )
        try:
            data = self.loader(self.path)
            if "entari" in data:
                data = data["entari"]
            basic = config_model_validate(BasicConfig, data.get("basic", {}))
            plugin = data.get("plugins", {})
            self.basic = basic
            self._origin_data = data
            self.plugin = plugin
            self._root_plugin_keys = {key.lstrip("?~") for key in plugin if not key.startswith("$")}
            self._extra_stems = {}
            self._reload_plugins()
            return True
        except Exception:
            (
                self.basic,
                self._origin_data,
                self.plugin,
                self.plugin_extra_files,
                self.prelude_plugin,
                self.plugin_prefixes,
                self._plugin_names,
                self._root_plugin_keys,
                self._extra_stems,
                records,
            ) = snapshot
            self._restore_records(records, replace_all=True)  # type: ignore
            raise

    def reload_file(
        self,
        path: str | os.PathLike[str] | None = None,
        *,
        force: bool = False,
    ) -> bool:
        if path is None:
            return self.reload(force=force)

        target = Path(path).resolve()
        if target == self.path.resolve():
            return self.reload(force=force)

        if self.save_flag:
            self.save_flag = False
            if not force:
                return False

        entry = self._find_extra_entry(target)
        if entry is None:
            return False  # 不是配置文件，或不在 $files 里

        if target.is_dir():
            stems = {file.stem for file in self._iter_extra_files(entry)}
            if stems & self._root_plugin_keys:
                # 目录里出现和主文件同名的插件：退化为整根，沿用现有覆盖语义
                return self.reload(force=force)
        elif target.stem in self._root_plugin_keys:
            # 主文件同名插件：退化为整根，沿用现有覆盖语义
            return self.reload(force=force)

        if target.is_dir():
            records_paths = self._iter_extra_files(entry)
        else:
            records_paths = [target]
        records_snapshot: dict[str, set[_EnvReplaced] | None] = {}
        for path in records_paths:
            key = path.resolve().as_posix()
            records = self._records.get(key)
            records_snapshot[key] = None if records is None else set(records)
        plugin_snapshot = deepcopy(self.plugin)
        meta_snapshot = (
            self.plugin_extra_files,
            self.prelude_plugin,
            self.plugin_prefixes,
            self._plugin_names,
            deepcopy(self._extra_stems),
        )
        stem = target.stem
        try:
            if target.is_dir():
                files = {file.stem: file for file in self._iter_extra_files(entry)}
                old = self._extra_stems.get(entry, set())
                for name in old - set(files):
                    self.plugin.pop(name, None)
                for name, file in files.items():
                    self.plugin[name] = self.loader(file)
                self._extra_stems[entry] = set(files)
            elif target.exists():
                self.plugin[stem] = self.loader(target)
                self._extra_stems.setdefault(entry, set()).add(stem)
            elif target.parent == self._resolve_extra(entry):
                # 目录条目下的文件被删除
                self.plugin.pop(stem, None)
                self._extra_stems.get(entry, set()).discard(stem)
            else:
                # 普通文件条目被删除：和整根 reload 一样报错
                raise FileNotFoundError(str(target))

            self._reload_plugins(load_files=False)
            return True
        except Exception:
            self.plugin = plugin_snapshot
            (
                self.plugin_extra_files,
                self.prelude_plugin,
                self.plugin_prefixes,
                self._plugin_names,
                self._extra_stems,
            ) = meta_snapshot
            self._restore_records(records_snapshot)
            raise

    @staticmethod
    def _clean(value: T_M) -> T_M:
        value.pop("$path", None)
        value.pop("$static", None)
        return value

    def dump(self, indent: int = 2, apply_schema: bool = False) -> dict[str, Any]:
        data = deepcopy(self._origin_data)
        basic = data.get("basic", {})
        plugins = data.get("plugins", {})
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
                    self.dumper(path, path, self._clean(plugins.pop(path.stem)), indent, apply_schema)
                else:
                    for _path in path.iterdir():
                        if _path.is_file() and not _path.name.endswith(".schema.json"):
                            self.dumper(_path, _path, self._clean(plugins.pop(_path.stem)), indent, apply_schema)
        for key in list(plugins.keys()):
            if key.startswith("$"):
                continue
            value = plugins.pop(key)
            if "$disable" in value and isinstance(value["$disable"], bool):
                key = f"~{key}" if value["$disable"] else key
                value.pop("$disable", None)
            if "$optional" in value:
                key = f"?{key}" if value["$optional"] else key
                value.pop("$optional", None)
            plugins[key] = self._clean(value)
        return data

    def save(self, path: str | os.PathLike[str] | None = None, indent: int = 2, apply_schema: bool = False):
        self.save_flag = True
        self.dumper(self.path, Path(path or self.path), self.dump(indent, apply_schema), indent, apply_schema)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None, detach: bool = False) -> "EntariConfig":
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
            return cls(_path, env_vars=env_vars, register_instance=not detach)
        if not _path.is_file():
            raise ValueError(f"{_path} is not a file")
        return cls(_path, env_vars=env_vars, register_instance=not detach)

    def bind(self, key: str, plugin: dict, obj: T) -> T:
        """
        Bind the plugin object to the config, allowing the config to be updated when the object changes.
        """
        if key not in self.plugin:
            for _, names in self._plugin_names.items():
                if key in names:
                    break
            else:
                raise KeyError(f"Plugin Config {key} not found in config")

        def updater(target):
            nest_dict_update(plugin, config_model_dump(target))
            self.save()
            self.save_flag = False
            self._reload_plugins()

        ans = Proxy(obj, lambda target=obj: updater(target))
        return ans  # type: ignore

    def generate_schema(self, plugins: list["Plugin"]):
        plugins_properties = {}
        # fmt: off
        # Build a mapping from plugin config key to plugin object for $files schema generation
        plugin_map: dict[str, "Plugin"] = {}  # noqa: UP037
        for plug in plugins:
            if plug.id == "$":
                schema = plugin_config_schema(plug, ref_root="/properties/plugins")
                for key, property_ in schema["properties"].items():
                    if key.startswith("$"):
                        continue
                    plugins_properties[key] = property_
            else:
                plugin_map[plug._config_key] = plug
                plugins_properties[plug._config_key] = plugin_config_schema(plug, ref_root=f"/properties/plugins/properties/{plug._config_key}/")  # noqa: E501
        schemas = {
            "basic": config_model_schema(BasicConfig, ref_root="/properties/basic/"), "plugins": {"type": "object", "description": "Plugin configurations", "properties": {"$prefix": {"description": "List of prefix config", "items": {"properties": {"key": {"description": "Prefix key", "title": "Key", "type": "string"}, "plugins": {"anyOf": [{"type": "string"}, {"items": {"type": "string", "description": "Plugin name"}, "type": "array", "uniqueItems": True}], "description": "List of plugins under the prefix, or select an item of $files to apply plugins", "title": "Plugins"}}, "required": ["key"], "title": "Prefix Config", "type": "object"}, "type": "array"}, "$prelude": {"type": "array", "items": {"type": "string", "description": "Plugin name"}, "description": "List of prelude plugins to load", "default": [], "uniqueItems": True}, "$files": {"type": "array", "items": {"type": "string", "description": "File path"}, "description": "List of configuration files to load", "default": [], "uniqueItems": True}, **plugins_properties}}, "adapters": {"type": "array", "description": "Adapter configurations", "items": {"type": "object", "description": "Adapter configuration", "properties": {"$path": {"type": "string", "description": "Adapter Module Path"}}, "required": ["$path"], "additionalProperties": True}}  # noqa: E501
        }
        with open(f"{self.path.stem}.schema.json", "w", encoding="utf-8") as f:
            json.dump({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": schemas, "additionalProperties": False, "required": ["basic"]}, f, indent=2, ensure_ascii=False)  # noqa: E501

        # fmt: on
        # Generate schema for each file in $files
        for file in self.plugin_extra_files:
            path = Path(file)
            if path.is_file() and not path.name.endswith(".schema.json"):
                self._generate_extra_file_schema(path, plugin_map)
            elif path.is_dir():
                for _path in path.iterdir():
                    if _path.is_file() and not _path.name.endswith(".schema.json"):
                        self._generate_extra_file_schema(_path, plugin_map)
        plugin_map.clear()

    def _generate_extra_file_schema(self, path: Path, plugin_map: dict[str, "Plugin"]):
        """Generate schema for an extra config file from $files."""
        plugin_key = path.stem
        schema_file = path.with_suffix(".schema.json")
        # fmt: off
        # Check if we have a matching plugin with config
        if plugin_key in plugin_map:
            plugin_schema = plugin_config_schema(plugin_map[plugin_key], use_extra_meta=True)
        else:
            # Plugin not found, generate a generic schema
            plugin_schema = {"type": "object", "description": f"Configuration for {plugin_key}", "additionalProperties": True, "properties":  {k: dict(v) for k, v in PLUGIN_META_PROPERTIES_EXTRA.items()}}  # noqa: E501
            apply_schema_fragments(plugin_schema, plugin_key, ref_root="/")

        with open(schema_file, "w", encoding="utf-8") as f:
            json.dump({"$schema": "https://json-schema.org/draft/2020-12/schema", **plugin_schema}, f, indent=2, ensure_ascii=False)  # noqa: E501
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
