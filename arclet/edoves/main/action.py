from contextlib import AsyncExitStack
from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod

if TYPE_CHECKING:
    from .medium import BaseMedium
    from .monomer import Monomer


class ExecutiveAction(metaclass=ABCMeta):
    action: str
    target: "Monomer"
    data: "BaseMedium"

    def __init__(self, medium: "BaseMedium", action: str):
        self.target = medium.purveyor
        self.data = medium
        self.action = action

    def __await__(self):
        return self.execute().__await__()

    @abstractmethod
    async def execute(self):
        raise NotImplementedError
