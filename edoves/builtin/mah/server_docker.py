from ...main.server_docker import BaseServerDocker, DockerBehavior, BaseDockerMetaComponent
from ...utilles.security import MIRAI_API_HTTP_DEFAULT
from ..client import AioHttpClient
from .protocol import MAHProtocol


class MAHDockerMeta(BaseDockerMetaComponent):
    protocol: MAHProtocol
    identifier: str = MIRAI_API_HTTP_DEFAULT
    session: AioHttpClient


class MAHBehavior(DockerBehavior):

    async def connect(self):
        pass

    def start(self):
        pass

    def session_handle(self):
        pass


class MAHServerDocker(BaseServerDocker[MAHProtocol]):
    prefab_metadata = MAHDockerMeta
    prefab_behavior = MAHBehavior
