import asyncio
from asyncio import Event
from ...main.server_docker import BaseServerDocker, DockerBehavior, BaseDockerMetaComponent
from ...utilles.security import MIRAI_API_HTTP_DEFAULT
from ..client import AioHttpClient, ClientWebSocketResponse
from .protocol import MAHProtocol
from ..event.network import DockerOperate


class MAHDockerMeta(BaseDockerMetaComponent):
    protocol: MAHProtocol
    identifier: str = MIRAI_API_HTTP_DEFAULT
    session: AioHttpClient


class MAHBehavior(DockerBehavior):
    data: MAHDockerMeta
    ws_conn: ClientWebSocketResponse
    start_ev: Event

    def activate(self):
        self.start_ev = Event()

        async def wait_start(operate: MAHDockerMeta.medium_type):
            while not operate.content.get("start"):
                await asyncio.sleep(0.01)
            self.start_ev.set()
            self.data.protocol.scene.edoves.logger.info("MAHServerDocker start!")

        self.io.new_handler(DockerOperate, wait_start)

    async def connect(self):
        self.data.protocol.scene.edoves.logger.info("MAHServerDocker connecting...")
        async with self.data.session.ensure_network(
                self.data.protocol.config.connection_url()
        ) as resp:
            await resp.read()

    async def start(self):
        await self.start_ev.wait()
        await self.data.protocol.test_set_message()
        try:
            await self.connect()
        except Exception as e:
            self.data.protocol.scene.edoves.logger.warning(e)

    async def session_handle(self) -> MAHDockerMeta.medium_type:
        pass


class MAHServerDocker(BaseServerDocker[MAHProtocol]):
    prefab_metadata = MAHDockerMeta
    prefab_behavior = MAHBehavior
