from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as field
from dataclasses import fields, is_dataclass
from inspect import Signature
import json
import os
from pathlib import Path
from typing import Any, Callable, ClassVar, TypedDict, TypeVar, get_args, get_origin
from typing_extensions import dataclass_transform
import warnings

_available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())


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
    plugin_extra_files: list[str] = field(default_factory=list, init=False)
    updater: Callable[[EntariConfig], None]

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
                import yaml
            except ImportError:
                raise RuntimeError("yaml is not installed")

            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        raise NotImplementedError(f"unsupported plugin config file format: {path!s}")

    def reload(self):
        self.updater(self)
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

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> EntariConfig:
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
        raise NotImplementedError(f"unsupported config file format: {_path!s}")


load_config = EntariConfig.load


_config_model_validators = {}

C = TypeVar("C")


def config_validator_register(base: type):
    def wrapper(func: Callable[[dict[str, Any], type[C]], C]):
        _config_model_validators[base] = func
        return func

    return wrapper


def config_model_validate(base: type[C], data: dict[str, Any]) -> C:
    for b in base.__mro__[-2::-1]:
        if b in _config_model_validators:
            return _config_model_validators[b](data, base)
    return base(**data)


@dataclass_transform(kw_only_default=True)
class BasicConfModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        dataclass(**{k: v for k, v in kwargs.items() if k in _available_dc_attrs})(cls)


@config_validator_register(BasicConfModel)
def _basic_config_validate(data: dict[str, Any], base: type[C]) -> C:
    def _nested_validate(namespace: dict[str, Any], cls):
        result = {}
        for field_ in fields(cls):
            if field_.name not in namespace:
                continue
            if is_dataclass(field_.type):
                result[field_.name] = _nested_validate(namespace[field_.name], field_.type)
            elif get_origin(field_.type) is list and is_dataclass(get_args(field_.type)[0]):
                result[field_.name] = [_nested_validate(d, get_args(field_.type)[0]) for d in namespace[field_.name]]
            elif get_origin(field_.type) is set and is_dataclass(get_args(field_.type)[0]):
                result[field_.name] = {_nested_validate(d, get_args(field_.type)[0]) for d in namespace[field_.name]}
            elif get_origin(field_.type) is dict and is_dataclass(get_args(field_.type)[1]):
                result[field_.name] = {
                    k: _nested_validate(v, get_args(field_.type)[1]) for k, v in namespace[field_.name].items()
                }
            elif get_origin(field_.type) is tuple:
                args = get_args(field_.type)
                result[field_.name] = tuple(
                    _nested_validate(d, args[i]) if is_dataclass(args[i]) else d
                    for i, d in enumerate(namespace[field_.name])
                )
            else:
                result[field_.name] = namespace[field_.name]
        return cls(**result)

    return _nested_validate(data, base)
