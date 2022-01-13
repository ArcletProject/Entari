from typing import Type, Generic
from abc import abstractmethod

from .network import NetworkClient
from ..builtin.medium import JsonMedium
from .typings import TNProtocol
from .module import BaseModule
from ..utilles import ModuleStatus


class BaseServerDocker(Generic[TNProtocol], BaseModule):
    protocol: TNProtocol
    medium_type: Type[JsonMedium]
    session: NetworkClient

    def __init__(self, protocol: TNProtocol):
        super().__init__(protocol)
        self.state = ModuleStatus.MEDIUM_WAIT

    @abstractmethod
    async def connect(self):
        async with self.session.ensure_network(
                self.protocol.config.get("host")
        ):
            raise NotImplementedError

    @abstractmethod
    def docker_start(self):
        medium = self.protocol.get_medium(self.medium_type)
        if medium.content.get("start"):
            return True

    def session_handle(self):
        pass
