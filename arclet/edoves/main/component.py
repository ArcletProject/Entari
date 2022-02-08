from typing import List, TYPE_CHECKING, Type, Union, Iterable

from .utilles import IOStatus
from .typings import TProtocol

if TYPE_CHECKING:
    from .interact import InteractiveObject, TC


class Component:
    __enable: bool = True
    io: "InteractiveObject"

    def __init__(self, io: "InteractiveObject"):
        self.io = io

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
        return self.__dict__.get(item)

    def __getattribute__(self, item):
        if item in ("is_enable", "set_active", "_Component__enable"):
            return super(Component, self).__getattribute__(item)
        if super().__getattribute__("_Component__enable"):
            return super(Component, self).__getattribute__(item)

    def __setattr__(self, key, value):
        if key == "__enable":
            super(Component, self).__setattr__(key, value)
        elif self.__enable:
            super(Component, self).__setattr__(key, value)

    def __delattr__(self, item):
        if self.__enable:
            super().__delattr__(item)

    def __repr__(self):
        return (
            f"[{self.__class__.__name__}: "
            f"{' '.join([f'{k}={v}' for k, v in vars(self).items() if k != 'io'])}]"
        )


class MetadataComponent(Component):
    tags: List[str]
    identifier: str
    protocol: TProtocol
    state: IOStatus

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
