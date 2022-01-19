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

    def summon_url(self, api: str, **kwargs: str):
        return self.connection_url() + f"/{api}" + \
               ("?" + "&".join([f"{k}={v}" for k, v in kwargs.items()])) if kwargs else ""

    def connection_url(self):
        return self.host + ":" + self.port
