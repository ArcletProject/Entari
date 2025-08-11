from abc import ABCMeta, abstractmethod
from dataclasses import asdict, fields
from typing import Any, Generic, TypeVar

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

    @classmethod
    @abstractmethod
    def schema(cls, t: type[C]) -> dict[str, Any]:
        """
        Get the schema of the configuration model.
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
    data = {k: v for k, v in data.items() if not k.startswith("$")}
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


def config_model_schema(base: type[C]) -> dict[str, Any]:
    for b in base.__mro__[-2::-1]:
        if b in _config_model_actions:
            return _config_model_actions[b].schema(base)
    return {field_.name: field_.type for field_ in fields(base)}  # type: ignore
