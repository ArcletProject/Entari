from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from inspect import Signature
from typing import Any, Callable, TypeVar, get_args, get_origin
from typing_extensions import dataclass_transform

_available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())

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
