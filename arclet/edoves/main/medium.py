from typing import Optional, Callable, Coroutine, Any
from .monomer import Monomer
from .typings import TMeta


class BaseMedium:
    purveyor: Monomer
    type: str
    content: TMeta

    __metadata__ = ["type", "content", "purveyor"]

    def create(self, purveyor: Monomer, content: Any, medium_type: Optional[str] = None, **kwargs):
        self.purveyor = purveyor
        self.type = medium_type or self.__class__.__name__
        self.content = content
        for k, v in kwargs.items():
            setattr(self, k, v)
        return self

    def action(self, method_name: str) -> Callable[..., Coroutine]:
        for func in [getattr(c, method_name, None) for c in self.purveyor.all_components]:
            if not func:
                continue
            return func

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; {', '.join([f'{k}={v}' for k, v in vars(self).items() if v])}>"
        )
