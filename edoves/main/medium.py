from typing import Type, Optional
from .monomer import Monomer
from .typings import TMeta


class BaseMedium:
    purveyor: Monomer
    type: str
    content: TMeta

    __metadata__ = "type", "content", "purveyor"

    @classmethod
    def create(cls, purveyor: Monomer, content_type: Type, medium_type: Optional[str] = None):
        def __wrapper(content: content_type):
            new_medium = cls()
            new_medium.purveyor = purveyor
            new_medium.type = medium_type or new_medium.__class__.__name__
            new_medium.content = content
            return new_medium
        return __wrapper

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; {', '.join([f'{k}={v}' for k, v in vars(self).items() if v])}>"
        )
