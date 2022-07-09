from typing import List, TYPE_CHECKING, Type, Union, Iterable, Dict, Any

from ..utilles import IOStatus


if TYPE_CHECKING:
    from ..interact import InteractiveObject, TC


class ComponentMeta(type):

    def __call__(cls, *args, **kwargs):
        obj: "Component" = cls.__new__(cls, *args, **kwargs)  # type: ignore
        _ignore = []
        _limit = []
        for m in cls.__mro__[-2::-1]:
            _ignore.extend(getattr(m, "__ignore__", []))
            _limit.extend(getattr(m, "__limit__", []))
        obj.__ignore__ = list(set(_ignore))
        obj.__limit__ = list(set(_limit))
        obj.__init__(*args, **kwargs)
        return obj


class Component:
    __enable: bool
    io: "InteractiveObject"
    additions: Dict[str, Any]

    __ignore__ = ["io"]
    __limit__ = []
    __required__ = []

    def __init__(self, io: "InteractiveObject"):
        self.__enable = True
        self.io = io
        self.additions = {}

    @property
    def interactive_object(self):
        return self.io

    @property
    def is_enable(self):
        return self.__enable

    def set_active(self, value: bool):
        self.__enable = value

    def get_component(self, __t: Union[str, Type["TC"]]) -> "TC":
        return self.interactive_object.get_component(__t)

    def __getitem__(self, item: str):
        return self.additions.get(item, None) or self.__dict__.get(item, None)

    def __getattr__(self, item):
        if attr := self.additions.get(item, None):
            return attr
        if item in ("is_enable", "set_active", "_Component__enable"):
            return self.__getattribute__(item)
        if self.__enable:
            return self.__getattribute__(item)
        else:
            raise AttributeError(f"Component {self.__class__.__name__} is not enable")

    def __setattr__(self, key, value):
        if key == "__enable":
            super(Component, self).__setattr__(key, value)
        elif self.__enable:
            if key not in ("__limit__", "__ignore__", "additions") and \
                    self.__limit__ and key not in self.__ignore__ + self.__limit__:
                self.additions[key] = value
            else:
                super(Component, self).__setattr__(key, value)
        else:
            raise AttributeError(f"Component {self.__class__.__name__} is not enable")

    def __delattr__(self, item):
        if self.__enable:
            if self.__limit__ and item not in self.__ignore__ + self.__limit__:
                del self.additions[item]
            else:
                super().__delattr__(item)
        else:
            raise AttributeError(f"Component {self.__class__.__name__} is not enable")

    def __repr__(self):
        attrs = [f'{k}={v}' for k, v in vars(self).items() if k not in self.__ignore__ and not k.startswith('_')]
        return (
            f"[{self.__class__.__name__}: "
            f"{' '.join(attrs)}]"
        )


class MetadataComponent(Component, metaclass=ComponentMeta):
    tags: List[str]
    identifier: str
    state: IOStatus

    __limit__ = ["tags", "identifier", "state"]

    def __init__(self, io: "InteractiveObject"):
        super().__init__(io)
        self.tags = []

    def add_tags(self, tags: Iterable[str]):
        if self.is_enable:
            self.tags.extend(set(tags).difference(self.tags))

    def remove_tags(self, tags: Iterable[str]):
        if self.is_enable:
            for t in tags:
                if t in self.tags:
                    self.tags.remove(t)
