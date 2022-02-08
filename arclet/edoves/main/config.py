from typing import Type
from .utilles import DataStructure
from .server_docker import NetworkClient
from .typings import TProtocol
from yarl import URL


class TemplateConfig(DataStructure):
    protocol: Type[TProtocol]
    client: Type[NetworkClient]
    verify_token: str
    account: int
    host: str = "http://localhost"
    port: str
    update_interval: float = 0.02
    modules_base_path: str = "./edoves_modules"
    ensure_retries: int = 5

    def get(self, key: str):
        return self.__dict__.get(key)

    def url(self, api: str, **kwargs: str):
        if not kwargs:
            return self.connection_url() / api
        return (self.connection_url() / api).with_query(kwargs)

    def connection_url(self):
        return URL(self.host + ":" + self.port)
