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

    def __await__(self):
        return self.execute().__await__()

    @abstractmethod
    async def execute(self):
        raise NotImplementedError
