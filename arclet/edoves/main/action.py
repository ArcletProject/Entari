from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod
from .context import ctx_monomer
from .monomer import Monomer, at_mono

if TYPE_CHECKING:
    from .medium import BaseMedium


class ExecutiveAction(metaclass=ABCMeta):
    action: str
    target: "Monomer"
    data: "BaseMedium"

    def __init__(self, action: str):
        self.action = action
        self.target = ctx_monomer.get()

    def to(self, target: "Monomer"):
        self.target = target
        return self

    @abstractmethod
    async def execute(self):
        raise NotImplementedError


class ExecAs:
    monomer: "Monomer"
    action: "ExecutiveAction"

    def __init__(self, target: "Monomer"):
        self.monomer = target

    def run(self, action: "ExecutiveAction"):
        self.action = action
        self.action.to(self.monomer)
        return self

    def __class_getitem__(cls, item):
        monomers = at_mono.__getitem__(item)
        if monomers:
            return cls(monomers[0])
        else:
            return cls(ctx_monomer.get())

    def __await__(self):
        return self.action.execute().__await__()


exec_as = ExecAs
