from typing import Type

from yarl import URL

from .interact.server_docker import BaseServerDocker
from .network import NetworkClient
from .typings import TProtocol
from .utilles import DataStructure


class TemplateConfig(DataStructure):
    protocol: Type[TProtocol]
    client: Type[NetworkClient]
    docker_type: Type["BaseServerDocker"]
    verify_token: str
    account: int
    host: str = "http://localhost"
    port: str
    update_interval: float = 0.02
    modules_base_path: str = "./edoves_modules"
    ensure_retries: int = 5
    use_event_record: bool = True

    def get(self, key: str):
        return self.__dict__.get(key)

    def url(self, api: str, **kwargs: str):
        return (self.connection_url() / api).with_query(kwargs) if kwargs else self.connection_url() / api

    def connection_url(self):
        return URL(f"{self.host}:{self.port}")
