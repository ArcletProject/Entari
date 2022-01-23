from typing import Dict, Type, Union, TypeVar, Optional, TypedDict, List, Set
from inspect import isclass
from .component import Component, MetadataComponent
from .behavior import BaseBehavior

TC = TypeVar("TC", bound=Component)


class Relationship(TypedDict):
    parents: Set["InteractiveObject"]
    children: Set["InteractiveObject"]


class InteractiveObject:
    prefab_behavior: Type[BaseBehavior] = BaseBehavior
    prefab_metadata: Type[MetadataComponent] = MetadataComponent
    _components: Dict[str, Component]
    metadata: prefab_metadata
    behavior: prefab_behavior
    relation: Relationship

    __slots__ = "metadata", "behavior", "_components", "relation"

    __ignore__ = ["_components", "relation"]

    def __new__(cls, *args, **kwargs):
        for __k in cls.__slots__:
            if __k in cls.__ignore__:
                continue
            if not issubclass(cls.__annotations__[__k], Component):
                raise ValueError
        return super().__new__(cls)

    def __init__(
            self,
            metadata: Optional[Union[prefab_metadata, Type[prefab_metadata]]] = None,
            behavior: Optional[Union[prefab_behavior, Type[prefab_behavior]]] = None
    ):
        self._components = {}
        self.relation = {"parents": set(), "children": set()}
        self.metadata = (
            metadata(self) if isclass(metadata) else metadata
        ) if metadata else self.prefab_metadata(self)
        self.behavior = (
            behavior(self) if isclass(behavior) else behavior
        ) if behavior else self.prefab_behavior(self)

    @property
    def parents(self):
        return self.relation['parents']

    @property
    def children(self):
        return self.relation['children']

    def set_parent(self, parent: "InteractiveObject"):
        parent.relation['children'].add(self)
        self.relation['parents'].add(parent)

    def set_child(self, child: "InteractiveObject"):
        child.relation['parents'].add(self)
        self.relation['children'].add(child)

    @property
    def all_components(self):
        return self._components.values()

    def get_component(self, __t: Union[str, Type[TC]]) -> TC:
        if isinstance(__t, str):
            return self._components.get(__t)
        for __c in filter(lambda x: isinstance(x, __t), list(self._components.values())):
            return __c

    def get_components(self, __t: Type[TC]) -> List[TC]:
        result = []
        for __c in filter(lambda x: isinstance(x, __t), list(self._components.values())):
            result.append(__c)
        return result

    def get_component_in_parent(self, __t: Union[str, Type[TC]]) -> TC:
        for __i in self.relation['parents']:
            if __c := __i.get_component(__t):
                return __c

    def get_component_in_children(self, __t: Union[str, Type[TC]]) -> TC:
        for __i in self.relation['children']:
            if __c := __i.get_component(__t):
                return __c

    def __getattr__(self, item):
        if item in self.__ignore__:
            return self.__getattribute__(item)
        return self._components.get(item)

    def __setattr__(self, key, value: Union[Dict[str, Component], Component]):
        if key in self.__ignore__:
            super(InteractiveObject, self).__setattr__(key, value)
        else:
            self._components.setdefault(key, value)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; "
            f"{', '.join([f'{k}={v}' for k, v in self._components.items()])}>"
        )
