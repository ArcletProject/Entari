from typing import Type, Optional
from ..utilles import DataStructure
from .server_docker import BaseServerDocker, NetworkClient
from .typings import TNProtocol


class TemplateConfig(DataStructure):
    protocol: Type[TNProtocol]
    server_docker: Optional[Type[BaseServerDocker]] = None
    client: Type[NetworkClient]
    verify_token: str
    account: int
    host: str = "http://localhost"
    port: str

    def get(self, key: str):
        return self.__dict__.get(key)
