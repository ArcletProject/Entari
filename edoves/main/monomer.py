from typing import Union, Optional
from .typings import TNProtocol


class Monomer:
    protocol: TNProtocol
    identifier: Union[int, str]
    name: str
    alias: str

    __metadata__ = "identifier", "name", "alias"

    def __init__(
            self,
            protocol: TNProtocol,
            name: str,
            identifier: Optional[Union[int, str]] = None,
            alias: Optional[str] = None
    ):
        self.protocol = protocol
        self.identifier = identifier or ""
        self.name = name
        self.alias = alias or ""

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; {', '.join([f'{k}={v}' for k, v in vars(self).items() if v])}>"
        )
