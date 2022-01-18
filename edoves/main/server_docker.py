from typing import Type, Generic
from abc import abstractmethod

from .network import NetworkClient
from ..builtin.medium import JsonMedium
from .typings import TNProtocol
from .module import BaseModule, ModuleMetaComponent, ModuleBehavior
from ..utilles import ModuleStatus
from ..utilles.security import UNKNOWN


class BaseDockerMetaComponent(ModuleMetaComponent):
    io: "BaseServerDocker"
    protocol: TNProtocol
    medium_type: Type[JsonMedium]
    session: NetworkClient
    identifier: str = UNKNOWN


class DockerBehavior(ModuleBehavior):
    io: "BaseServerDocker"
    data: BaseDockerMetaComponent

    def __init__(self, io: "BaseServerDocker"):
        super().__init__(io)
        self.data = self.get_component(BaseDockerMetaComponent)

    @abstractmethod
    async def connect(self):
        async with self.data.session.ensure_network(
                self.data.protocol.config.get("host")
        ):
            raise NotImplementedError

    @abstractmethod
    def start(self):
        medium = self.data.protocol.get_medium(self.data.medium_type)
        if medium.content.get("start"):
            return True

    @abstractmethod
    def session_handle(self):
        pass


class BaseServerDocker(BaseModule, Generic[TNProtocol]):
    prefab_metadata = BaseDockerMetaComponent
    prefab_behavior = DockerBehavior

    def __init__(self, protocol: TNProtocol, client: NetworkClient):
        super().__init__(protocol)
        data = self.get_component(BaseDockerMetaComponent)
        data.state = ModuleStatus.MEDIUM_WAIT
        data.session = client
