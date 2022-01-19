import asyncio

from ...main.server_docker import BaseServerDocker, DockerBehavior, BaseDockerMetaComponent
from ...utilles.security import MIRAI_API_HTTP_DEFAULT
from ..client import AioHttpClient
from .protocol import MAHProtocol


class MAHDockerMeta(BaseDockerMetaComponent):
    protocol: MAHProtocol
    identifier: str = MIRAI_API_HTTP_DEFAULT
    session: AioHttpClient


class MAHBehavior(DockerBehavior):
    data: MAHDockerMeta

    async def connect(self):
        self.data.protocol.edoves.logger.info("MAHServerDocker connecting...")
        async with self.data.session.ensure_network(
                self.data.protocol.config.connection_url()
        ) as resp:
            await resp.read()

    async def start(self):
        medium = await self.data.protocol.get_medium(self.data.medium_type)
        while not medium.content.get("start"):
            await asyncio.sleep(0.01)
        self.data.protocol.edoves.logger.info("MAHServerDocker start!")
        try:
            await self.connect()
        except Exception as e:
            self.data.protocol.edoves.logger.warning(e)

    async def session_handle(self):
        pass


class MAHServerDocker(BaseServerDocker[MAHProtocol]):
    prefab_metadata = MAHDockerMeta
    prefab_behavior = MAHBehavior
