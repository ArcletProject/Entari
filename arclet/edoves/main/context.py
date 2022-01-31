from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generic, Union, TypeVar, TYPE_CHECKING

from arclet.edoves.utilles import T

D = TypeVar("D")


class ContextModel(Generic[T]):
    current_ctx: ContextVar[T]

    def __init__(self, name: str) -> None:
        self.current_ctx = ContextVar(name)

    def get(self, default: Union[T, D] = None) -> Union[T, D]:
        return self.current_ctx.get(default)

    def set(self, value: T):
        return self.current_ctx.set(value)

    def reset(self, token: Token):
        return self.current_ctx.reset(token)

    @contextmanager
    def use(self, value: T):
        token = self.set(value)
        yield
        self.reset(token)


if TYPE_CHECKING:
    from . import Edoves
    from .module import BaseModule
    from .monomer import Monomer

ctx_edoves: "ContextModel[Edoves]" = ContextModel("edoves")
ctx_module: "ContextModel[BaseModule]" = ContextModel("module")
ctx_monomer: "ContextModel[Monomer]" = ContextModel("purveyor")
