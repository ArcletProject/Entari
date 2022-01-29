from typing import Type, Generic, Dict, Any, Union, Optional
from abc import abstractmethod

from aiohttp import FormData

from .network import NetworkClient, HTTP_METHODS
from ..builtin.medium import JsonMedium
from .typings import TNProtocol
from .module import BaseModule, ModuleMetaComponent, ModuleBehavior
from ..utilles import IOStatus
from ..utilles.security import UNKNOWN


class BaseDockerMetaComponent(ModuleMetaComponent):
    io: "BaseServerDocker"
    protocol: TNProtocol
    medium_type: Type[JsonMedium] = JsonMedium
    session: NetworkClient
    verify_code: str = UNKNOWN


class DockerBehavior(ModuleBehavior):
    io: "BaseServerDocker"
    data: BaseDockerMetaComponent

    def __init__(self, io: "BaseServerDocker"):
        super().__init__(io)
        self.data = self.get_component(BaseDockerMetaComponent)

    async def connect(self):
        async with self.data.session.ensure_network(
                self.data.protocol.config.get("host")
        ):
            raise NotImplementedError

    @abstractmethod
    async def start(self):
        _ = await self.data.protocol.get_medium(medium_type=self.data.medium_type)
        raise NotImplementedError

    @abstractmethod
    async def session_handle(
            self,
            method: HTTP_METHODS,
            action: str,
            content: Optional[Union[Dict[str, Any], str, FormData]] = None,
            **kwargs
    ):
        async with self.data.session.request(
            method,
            self.data.protocol.config.url(action, **content),
            **kwargs
        ):
            raise NotImplementedError


class BaseServerDocker(BaseModule, Generic[TNProtocol]):
    prefab_metadata = BaseDockerMetaComponent
    prefab_behavior = DockerBehavior

    def __init__(self, protocol: TNProtocol, client: NetworkClient):
        super().__init__(protocol)
        data = self.get_component(BaseDockerMetaComponent)
        data.state = IOStatus.MEDIUM_WAIT
        data.session = client
