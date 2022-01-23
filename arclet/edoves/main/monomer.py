from abc import abstractmethod
from typing import Union, Optional, Callable, Any, Coroutine

from .typings import TMonoProtocol
from .interact import InteractiveObject
from .component import MetadataComponent
from .behavior import BaseBehavior


class MonoMetaComponent(MetadataComponent):
    io: "Monomer"
    protocol: TMonoProtocol
    name: str
    alias: str


class BaseMonoBehavior(BaseBehavior):
    io: "Monomer"

    @abstractmethod
    def activate(self):
        ...

    async def update(self):
        pass
        raise NotImplementedError


class Monomer(InteractiveObject):
    prefab_metadata = MonoMetaComponent
    prefab_behavior = BaseMonoBehavior

    def __init__(
            self,
            protocol: TMonoProtocol,
            name: str,
            identifier: Optional[Union[int, str]] = None,
            alias: Optional[str] = None,

    ):
        data = self.prefab_metadata(self)
        data.protocol = protocol
        data.identifier = identifier or ""
        data.name = name
        data.alias = alias or ""
        super(Monomer, self).__init__(data)

    def add_tags(self, *tag: str):
        self.metadata.add_tags(tag)

    def action(self, method_name: str) -> Callable[[Any, Any], Coroutine]:
        for func in [getattr(c, method_name, None) for c in self.all_components]:
            if not func:
                continue
            return func
