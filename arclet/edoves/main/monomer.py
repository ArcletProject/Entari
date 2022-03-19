from abc import abstractmethod
from typing import Union, Optional, Any, List, Coroutine
import inspect

from .typings import TProtocol
from .interact import InteractiveObject, IOManager
from .component import MetadataComponent
from .behavior import BaseBehavior
from .utilles import IOStatus


class MonoMetaComponent(MetadataComponent):
    io: "Monomer"
    name: str
    alias: str

    __limit__ = ["name", "alias"]

    def __getitem__(self, item: str) -> Union[Any, Coroutine[Any, Any, Any]]:
        res = self.additions.get(item, None) or self.__dict__.get(item, None)
        if res is None:
            return self.protocol.put_metadata(item, self.io)
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
        data = self.prefab_metadata(self)
        data.protocol = protocol
        data.identifier = f"{identifier}@{protocol.identifier}"
        data.name = name
        data.alias = alias or ""
        super(Monomer, self).__init__(data)
        self.metadata.state = IOStatus.ESTABLISHED

    def __getitem__(self, item: str):
        parts = item.split(".")
        if len(parts) == 1:
            return self.metadata.__getitem__(item)
        tag, attr = parts[0], parts[1]
        if self.compare(tag):
            return self.metadata.__getitem__(item)

    def __setstate__(self, state):
        f = inspect.currentframe()
        lcs = f.f_back.f_back.f_locals
        self.__init__(
            lcs['self'].protocol,
            state['metadata']['name'],
            state['metadata']['identifier'].split("@")[0],
            state['metadata']['alias']
        )
        self.add_tags(*state['metadata']['tags'])


class _EntitySelect:

    def __getitem__(self, item) -> List["Monomer"]:
        monomers: List["Monomer"] = IOManager.filter(Monomer)
        conditions = []
        slices = list(item) if not isinstance(item, slice) else [item]
        for sl in slices:
            key, value = sl.start, str(sl.stop)
            if key in ("id", "uid", "identifier"):
                def _(monomer: "Monomer", _value=value):
                    return monomer.metadata.pure_id == _value
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


at_mono = _EntitySelect()
