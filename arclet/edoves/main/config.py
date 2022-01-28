from typing import Type, Optional
from ..utilles import DataStructure
from .server_docker import BaseServerDocker, NetworkClient
from .typings import TNProtocol
from yarl import URL


class TemplateConfig(DataStructure):
    protocol: Type[TNProtocol]
    server_docker: Optional[Type[BaseServerDocker]] = None
    client: Type[NetworkClient]
    verify_token: str
    account: int
    host: str = "http://localhost"
    port: str
    update_interval: float = 0.02
    modules_path: str = "./modules"

    def get(self, key: str):
        return self.__dict__.get(key)

    def url(self, api: str, **kwargs: str):
        if not kwargs:
            return self.connection_url() / api
        return (self.connection_url() / api).with_query(kwargs)

    def connection_url(self):
        return URL(self.host + ":" + self.port)
