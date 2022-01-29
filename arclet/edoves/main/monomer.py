from abc import abstractmethod
from typing import Union, Optional, Callable, Coroutine, Any
import inspect

from .typings import TMonoProtocol
from .interact import InteractiveObject
from .component import MetadataComponent
from .behavior import BaseBehavior
from .action import ExecutiveAction
from ..utilles import IOStatus


class MonoMetaComponent(MetadataComponent):
    io: "Monomer"
    protocol: TMonoProtocol
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
            protocol: TMonoProtocol,
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

    def action(self, method_name: str) -> Callable[..., Coroutine]:
        for func in [getattr(c, method_name, None) for c in self.all_components]:
            if not func:
                continue
            return func

    @staticmethod
    async def execute(action: ExecutiveAction):
        return await action.execute()

    def __getstate__(self):
        return {
            "metadata": {k: v for k, v in self.metadata.__dict__.items() if k not in ("io", "protocol")},
            "behavior": self.prefab_behavior
        }

    def __setstate__(self, state):
        f = inspect.currentframe()
        lcs = f.f_back.f_back.f_locals
        self.__init__(
            lcs['self'].monomer_protocol,
            state['metadata']['name'],
            state['metadata']['identifier'],
            state['metadata']['alias']
        )
        self.add_tags(*state['metadata']['tags'])
