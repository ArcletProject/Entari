from typing import Dict, Type, Union, TypeVar
from .component import Component, MetadataComponent
from .behavior import BaseBehavior
from .typings import TProtocol
from ..utilles.security import UNKNOWN, IdentifierChecker

TC = TypeVar("TC", bound=Component)


class BasicIOMetadata(MetadataComponent, metaclass=IdentifierChecker):
    identifier: str = UNKNOWN
    protocol: TProtocol


class InteractiveObject:
    prefab_behavior: Type[BaseBehavior] = BaseBehavior
    prefab_metadata: Type[MetadataComponent] = MetadataComponent
    _components: Dict[str, Component]
    metadata: prefab_metadata
    behavior: prefab_behavior

    __slots__ = "metadata", "behavior", "_components"

    def __new__(cls, *args, **kwargs):
        for __k in cls.__slots__:
            if __k == "_components":
                continue
            if not issubclass(cls.__annotations__[__k], Component):
                raise ValueError
        return super().__new__(cls)

    def __init__(
            self,
            metadata: Union[prefab_metadata, Type[prefab_metadata]],
            behavior: Union[prefab_behavior, Type[prefab_behavior]]
    ):
        self._components = {}
        self.metadata = metadata if isinstance(metadata, self.prefab_metadata) else metadata(self)
        self.behavior = behavior if isinstance(behavior, self.prefab_behavior) else behavior(self)

    def get_component(self, __t: Union[str, Type[TC]]) -> TC:
        if isinstance(__t, str):
            return self._components.get(__t)
        for __c in filter(lambda x: isinstance(x, __t), list(self._components.values())):
            return __c

    def __getattr__(self, item):
        if item == "_components":
            return self._components
        return self._components.get(item)

    def __setattr__(self, key, value: Union[Dict[str, Component], Component]):
        if key == "_components":
            super(InteractiveObject, self).__setattr__("_components", value)
        self._components.setdefault(key, value)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; "
            f"{', '.join([f'{k}={v}' for k, v in self._components.items() if k != '_components'])}>"
        )
