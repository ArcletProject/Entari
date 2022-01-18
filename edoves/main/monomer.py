from abc import abstractmethod
from typing import Union, Optional

from .typings import TNProtocol
from .interact import InteractiveObject
from .component import MetadataComponent
from .behavior import BaseBehavior


class MonoMetaComponent(MetadataComponent):
    io: "Monomer"
    protocol: TNProtocol
    identifier: Union[int, str]
    name: str
    alias: str


class BaseMonoBehaviour(BaseBehavior):
    io: "Monomer"

    @abstractmethod
    def activate(self):
        ...

    async def update(self):
        pass
        raise NotImplementedError


class Monomer(InteractiveObject):
    prefab_metadata = MonoMetaComponent
    prefab_behavior = BaseMonoBehaviour

    def __init__(
            self,
            protocol: TNProtocol,
            name: str,
            identifier: Optional[Union[int, str]] = None,
            alias: Optional[str] = None,

    ):
        data = self.prefab_metadata(self)
        data.protocol = protocol
        data.identifier = identifier or ""
        data.name = name
        data.alias = alias or ""
        super(Monomer, self).__init__(data, self.prefab_behavior)

    def add_tags(self, *tag: str):
        self.metadata.add_tags(tag)
