from typing import Type, Optional
from ..utilles import DataStructure
from .dock_server import BaseDockServer
from .typings import TNProtocol


class TemplateConfig(DataStructure):
    protocol: Type[TNProtocol]
    dock_server: Optional[Type[BaseDockServer]] = None
    verify_token: str
    account: int
    host: str = "http://localhost"
    port: str

    def get(self, key: str):
        return self.__dict__.get(key)
