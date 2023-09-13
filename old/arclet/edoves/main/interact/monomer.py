from abc import abstractmethod
from typing import Union, Optional, Any, List, Coroutine
import inspect

from . import InteractiveObject, IOManager
from ..typings import TProtocol
from ..component import MetadataComponent
from ..component.behavior import BaseBehavior
from ..utilles import IOStatus


class MonoMetaComponent(MetadataComponent):
    io: "Monomer"
    name: str
    alias: str

    __limit__ = ["name", "alias"]

    def __getitem__(self, item: str) -> Union[Any, Coroutine[Any, Any, Any]]:
        res = self.additions.get(item, None) or self.__dict__.get(item, None)
        if res is None:
            return self.io.protocol.put_metadata(item, self.io)
        return res


class BaseMonoBehavior(BaseBehavior):
    io: "Monomer"

    @abstractmethod
    def activate(self):
        ...

    @abstractmethod
    async def change_metadata(
            self,
            meta: str,
            value: Any,
            target: Optional["Monomer"] = None,
            **addition
    ):
        await self.io.protocol.set_metadata(meta, value, target or self.io, **addition)
        raise NotImplementedError

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
            identifier: Union[int, str],
            alias: Optional[str] = None,

    ):
        self.protocol = protocol
        data = self.prefab_metadata(self)
        data.identifier = str(identifier)
        data.name = name
        data.alias = alias or ""
        super(Monomer, self).__init__(data)
        self.metadata.state = IOStatus.ESTABLISHED

    def __getitem__(self, item: str):
        parts = item.split(".")
        if len(parts) == 1:
            return self.metadata.__getitem__(item)
        tag, attr = parts[0], parts[1]
        if self.compare(tag.lower()):
            return self.metadata.__getitem__(item)

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


def at_mono(**kwargs):
    monomers: List["Monomer"] = IOManager.filter(Monomer)
    conditions = []
    for key, value in kwargs.items():
        value = str(value)
        if key in ("id", "uid", "identifier"):
            def _(monomer: "Monomer", _value=value):
                return monomer.metadata.identifier == _value
        elif key == "tag":
            def _(monomer: "Monomer", _value=value):
                return monomer.prime_tag == _value
        elif key == "type":
            def _(monomer: "Monomer", _value=value):
                return monomer.__class__.__name__ == _value
        else:
            def _(monomer: "Monomer", _key=key, _value=value):
                return getattr(monomer.metadata, _key, None) == _value

        conditions.append(_)
    return list(filter(lambda x: all([condition(x) for condition in conditions]), monomers))


class _EntitySelect:

    def __getitem__(self, item) -> List["Monomer"]:
        return at_mono(**{
            sl.start: sl.stop for sl in filter(lambda x: isinstance(x, slice), item)
        })


select = _EntitySelect()
