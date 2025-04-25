from abc import ABCMeta, abstractmethod
from dataclasses import asdict, dataclass, fields, is_dataclass
from inspect import Signature
from typing import Any, Generic, TypeVar, get_args, get_origin
from typing_extensions import dataclass_transform

_available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())

_config_model_actions: dict[type, type["ConfigModelAction"]] = {}

C = TypeVar("C")


class ConfigModelAction(Generic[C], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def load(cls, data: dict[str, Any], t: type[C]) -> C:
        """
        Validate the configuration data and return a model instance.
        """
        pass

    @classmethod
    @abstractmethod
    def dump(cls, obj: C) -> dict[str, Any]:
        """
        Update the configuration data from the model instance.
        """
        pass

    @classmethod
    @abstractmethod
    def keys(cls, obj: C) -> list[str]:
        """
        Get the keys of the configuration model.
        """
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
        if cls.__orig_bases__[0].__args__[0] is C:  # type: ignore
            raise TypeError("Subclass of ConfigModelAction must be generic.")
        base = cls.__orig_bases__[0].__args__[0]  # type: ignore
        _config_model_actions[base] = cls
        return cls


class Proxy:
    def __init__(self, origin, updater):
        self.__origin = origin
        self.__updater = updater

    def __getattr__(self, item):
        res = getattr(self.__origin, item)
        if isinstance(res, (list, tuple, set, dict, self.__origin.__class__)):
            return Proxy(res, self.__updater)
        return res

    def __getitem__(self, item):
        res = self.__origin[item]
        if isinstance(res, (list, tuple, set, dict, self.__origin.__class__)):
            return Proxy(res, self.__updater)
        return res

    def __setattr__(self, key, value):
        if key in {"_Proxy__origin", "_Proxy__updater"}:
            super().__setattr__(key, value)
        else:
            setattr(self.__origin, key, value)
            self.__updater()

    def __setitem__(self, key, value):
        self.__origin[key] = value
        self.__updater()

    def __repr__(self):
        return self.__origin.__repr__()

    def __str__(self):
        return self.__origin.__str__()

    def __len__(self):
        return len(self.__origin)

    def __contains__(self, item):
        return item in self.__origin

    def __iter__(self):
        return self.__origin.__iter__()

    def __eq__(self, other):
        if isinstance(other, Proxy):
            return self.__origin == other._Proxy__origin
        return self.__origin == other

    def __bool__(self):
        return bool(self.__origin)


def config_model_validate(base: type[C], data: dict[str, Any]) -> C:
    for b in base.__mro__[-2::-1]:
        if b in _config_model_actions:
            return _config_model_actions[b].load(data, base)
    return base(**data)  # type: ignore


def config_model_dump(obj: Any) -> dict[str, Any]:
    for b in obj.__class__.__mro__[-2::-1]:
        if b in _config_model_actions:
            return _config_model_actions[b].dump(obj)
    return asdict(obj)  # type: ignore


def config_model_keys(obj: Any) -> list[str]:
    for b in obj.__class__.__mro__[-2::-1]:
        if b in _config_model_actions:
            return _config_model_actions[b].keys(obj)
    return [field_.name for field_ in fields(obj)]  # type: ignore


@dataclass_transform(kw_only_default=True)
class BasicConfModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        dataclass(**{k: v for k, v in kwargs.items() if k in _available_dc_attrs})(cls)


class BasicConfModelAction(ConfigModelAction[BasicConfModel]):
    @classmethod
    def load(cls, data: dict[str, Any], base: type[C]) -> C:
        def _nested_validate(namespace: dict[str, Any], cls_):
            result = {}
            for field_ in fields(cls_):
                if field_.name not in namespace:
                    continue
                if is_dataclass(field_.type):
                    result[field_.name] = _nested_validate(namespace[field_.name], field_.type)
                elif get_origin(field_.type) is list and is_dataclass(get_args(field_.type)[0]):
                    result[field_.name] = [
                        _nested_validate(d, get_args(field_.type)[0]) for d in namespace[field_.name]
                    ]
                elif get_origin(field_.type) is set and is_dataclass(get_args(field_.type)[0]):
                    result[field_.name] = {
                        _nested_validate(d, get_args(field_.type)[0]) for d in namespace[field_.name]
                    }
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
            return cls_(**result)

        return _nested_validate(data, base)

    @classmethod
    def dump(cls, obj: BasicConfModel) -> dict[str, Any]:
        return asdict(obj)  # type: ignore

    @classmethod
    def keys(cls, obj: BasicConfModel) -> list[str]:
        return [field_.name for field_ in fields(obj)]  # type: ignore
