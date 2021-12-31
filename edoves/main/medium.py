from .monomer import Monomer
from .typings import TMeta


class BaseMedium:
    purveyor: Monomer
    type: str
    content: TMeta

    __metadata__ = "type", "content", "purveyor"

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; {', '.join([f'{k}={v}' for k, v in vars(self).items() if v])}>"
        )
