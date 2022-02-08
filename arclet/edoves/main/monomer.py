from abc import abstractmethod
from typing import Union, Optional, Any
import inspect

from .typings import TProtocol
from .interact import InteractiveObject
from .component import MetadataComponent
from .behavior import BaseBehavior
from .action import ExecActionWrapper
from .utilles import IOStatus


class MonoMetaComponent(MetadataComponent):
    io: "Monomer"
    name: str
    alias: str

    def update_data(self, name: str, value: Any):
        if not self.__dict__.get(name):
            setattr(self, name, value)
        self.__dict__[name] = value


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
    metadata: MonoMetaComponent
    behavior: BaseMonoBehavior

    def __init__(
            self,
            protocol: TProtocol,
            name: str,
            identifier: Optional[Union[int, str]] = None,
            alias: Optional[str] = None,

    ):
        data = self.prefab_metadata(self)
        data.protocol = protocol
        data.identifier = str(identifier) or ""
        data.name = name
        data.alias = alias or ""
        super(Monomer, self).__init__(data)
        self.metadata.state = IOStatus.ESTABLISHED

    @property
    def execute(self):
        return ExecActionWrapper(self)

    def __setstate__(self, state):
        f = inspect.currentframe()
        lcs = f.f_back.f_back.f_locals
        self.__init__(
            lcs['self'].protocol,
            state['metadata']['name'],
            state['metadata']['identifier'],
            state['metadata']['alias']
        )
        self.add_tags(*state['metadata']['tags'])
