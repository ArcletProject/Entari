from typing import Dict, Any, Union, Optional
from abc import abstractmethod
from aiohttp import FormData

from .module import BaseModule, ModuleMetaComponent, ModuleBehavior
from ..network import NetworkClient, HTTP_METHODS, NetworkStatus
from ..medium import BaseMedium
from ..typings import TProtocol
from ..utilles import IOStatus
from ..utilles.security import UNKNOWN


class BaseDockerMetaComponent(ModuleMetaComponent):
    io: "BaseServerDocker"
    client: NetworkClient
    verify_code: str = UNKNOWN
    state: Union[IOStatus, NetworkStatus]


class DockerBehavior(ModuleBehavior):
    io: "BaseServerDocker"
    data: BaseDockerMetaComponent

    def __init__(self, io: "BaseServerDocker"):
        super().__init__(io)
        self.data = self.get_component(BaseDockerMetaComponent)

    @abstractmethod
    async def session_fetch(self) -> Optional[BaseMedium]:
        raise NotImplementedError

    @abstractmethod
    async def connect(self):
        async with self.data.client.ensure_network(
                self.io.protocol.current_scene.config.get("host")
        ):
            raise NotImplementedError

    @abstractmethod
    async def session_handle(
            self,
            method: HTTP_METHODS,
            action: str,
            content: Optional[Union[Dict[str, Any], str, FormData]] = None,
            **kwargs
    ):
        async with self.data.client.request(
            method,
            self.io.protocol.current_scene.config.url(action, **content),
            **kwargs
        ):
            raise NotImplementedError

    async def update(self):
        data = await self.session_fetch()
        if not data:
            return
        for p in self.io.protocol.parsers:
            if p.metadata.chosen_parser(self.io.protocol.event_type_predicate(data.content)):
                await p.behavior.from_docker(self.io.protocol, data)


class BaseServerDocker(BaseModule):
    prefab_metadata = BaseDockerMetaComponent
    prefab_behavior = DockerBehavior
    behavior: DockerBehavior
    metadata: BaseDockerMetaComponent

    def __init__(self, protocol: TProtocol, client: NetworkClient):
        super().__init__(protocol)
        data = self.get_component(BaseDockerMetaComponent)
        data.state = IOStatus.MEDIUM_GET_WAIT
        data.client = client
