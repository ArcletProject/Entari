from typing import Generic, TypeVar, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Edoves

CK = TypeVar("CK")
CO = TypeVar("CO")


class Controller(Generic[CK, CO]):
    edoves: "Edoves"
    _CO_store: Dict[CK, CO]
    _CO_current: CO = None

    def __init__(self, edoves: "Edoves"):
        self.edoves = edoves
        self._CO_store = {}

    def add(self, __k: CK, __o: CO):
        self._CO_store[__k] = __o
        self._CO_current = __o

    def get(self, k: Optional[CK]) -> CO:
        if not k:
            return self._CO_current
        return self._CO_store.get(k)

    def remove(self, k: Optional[CK]):
        if not k:
            self._CO_current = None
        self._CO_store.pop(k)

    def pop(self, k: CK) -> CO:
        return self._CO_store.pop(k)

    def traverse(self):
        for v in self._CO_store.values():
            yield v

    @property
    def current(self):
        return self._CO_current

    def __repr__(self):
        return "{" + ",".join([f"{v}" for v in self._CO_store.values() if v is not None]) + "}"
