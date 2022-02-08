from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod
from .context import ctx_monomer

if TYPE_CHECKING:
    from .medium import BaseMedium
    from .monomer import Monomer


class ExecutiveAction(metaclass=ABCMeta):
    action: str
    target: "Monomer"
    data: "BaseMedium"

    def __init__(self, action: str):
        self.action = action
        self.target = ctx_monomer.get()

    def set_target(self, target: "Monomer"):
        self.target = target

    # def __await__(self):
    #     return self.execute().__await__()

    @abstractmethod
    async def execute(self):
        raise NotImplementedError


class ExecActionWrapper:
    monomer: "Monomer"
    action: "ExecutiveAction"

    def __init__(self, target: "Monomer"):
        self.monomer = target

    def execute(self, action: "ExecutiveAction"):
        self.action = action
        return self

    def to(self, target: "Monomer"):
        self.action.set_target(target)
        return self

    __call__ = execute

    def __await__(self):
        return self.action.execute().__await__()
