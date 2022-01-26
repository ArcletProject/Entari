from abc import ABCMeta, abstractmethod
from .medium import BaseMedium
from .monomer import Monomer


class ExecutiveAction(metaclass=ABCMeta):
    target: Monomer
    data: BaseMedium

    def __init__(self, medium: BaseMedium):
        self.target = medium.purveyor
        self.data = medium

    @abstractmethod
    async def execute(self):
        raise NotImplementedError
