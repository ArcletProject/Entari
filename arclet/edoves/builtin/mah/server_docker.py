import asyncio
import json
from asyncio import Event
from typing import Optional, Union, Dict, Any, Tuple
from aiohttp import FormData, WSMsgType
from ...main.server_docker import BaseServerDocker, DockerBehavior, BaseDockerMetaComponent
from ...utilles.logger import Logger
from ...utilles import IOStatus, error_check, DatetimeEncoder
from ...utilles.security import MIRAI_API_HTTP_DEFAULT
from ..client import AioHttpClient, ClientWebSocketResponse
from .protocol import MAHProtocol
from ..event.network import DockerOperate


class MAHDockerMeta(BaseDockerMetaComponent):
    protocol: MAHProtocol
    identifier: str = MIRAI_API_HTTP_DEFAULT
    session: AioHttpClient
    session_key: str = None


class MAHBehavior(DockerBehavior):
    data: MAHDockerMeta
    ws_conn: ClientWebSocketResponse
    start_ev: Event
    logger: Logger.logger

    def activate(self):
        self.start_ev = Event()

        async def wait_start(operate: MAHDockerMeta.medium_type):
            while not operate.content.get("start"):
                await asyncio.sleep(0.01)
            self.start_ev.set()
            self.data.protocol.scene.edoves.logger.info("MAHServerDocker start!")

        self.io.new_handler(DockerOperate, wait_start)

    async def connect(self):
        self.logger.info("MAHServerDocker connecting...")
        async with self.data.session.ensure_network(
                self.data.protocol.config.url(
                    "all",
                    qq=str(self.data.protocol.config.account),
                    verifyKey=str(self.data.protocol.config.verify_token)
                )
        ) as resp:
            connection = await resp.execute("get_connection")
            self.ws_conn = connection
            self.logger.info("MAHServerDocker connected.")

    async def start(self):
        self.logger = self.data.protocol.scene.edoves.logger
        await self.start_ev.wait()
        try:
            await self.connect()
        except Exception as e:
            self.logger.warning(e)

    async def update(self):
        try:
            ws_message = await self.ws_conn.receive(timeout=60.0)
        except asyncio.TimeoutError:
            try:
                try:
                    self.logger.debug("websocket: trying ping...")
                    await self.ws_conn.ping()
                except Exception as e:
                    self.logger.exception(f"websocket: ping failed: {e!r}")
                else:
                    return
            except asyncio.CancelledError:
                self.logger.warning("websocket: cancelled, stop")
                self.data.state = IOStatus.CLOSED
        else:
            if ws_message.type is WSMsgType.TEXT:
                received_data: dict = json.loads(ws_message.data)
                if self.data.session_key:
                    try:
                        await self.data.protocol.parse_raw_data(received_data.get('data'))
                    except Exception as e:
                        self.logger.exception(f"receive_data has error {e}")
                else:
                    if not received_data['syncId']:
                        data = received_data['data']
                        if data['code']:
                            error_check(data)
                        self.data.session_key = data.get("session")
            elif ws_message.type is WSMsgType.CLOSE:
                self.logger.info("websocket: server close connection.")
                self.data.state = IOStatus.CLOSED
                return
            elif ws_message.type is WSMsgType.CLOSED:
                self.logger.info("websocket: connection has been closed.")
                self.data.state = IOStatus.CLOSED
                return
            elif ws_message.type is WSMsgType.PONG:
                self.logger.debug("websocket: received pong from remote")
            elif ws_message.type == WSMsgType.ERROR:
                self.logger.warning("websocket: connection error: " + ws_message.data)
            else:
                self.logger.warning(f"detected a unknown message type: {ws_message.type}")

    async def quit(self):
        await self.ws_conn.close()
        self.logger.info("connection disconnected")

    async def session_handle(
            self,
            method: str,
            action: str,
            content: Optional[Union[Dict[str, Any], str, FormData]] = None,
            **kwargs
    ):
        content = content or {}
        if not self.data.session:
            raise RuntimeError("Unable to get session!")

        if method in ("GET", "get"):
            if isinstance(content, str):
                content = json.loads(content)
            async with self.data.session.get(
                self.data.protocol.config.url(action, **content)
            ) as response:
                resp_json: dict = await response.execute("get_json")

        elif method in ("POST", "Update"):
            if not isinstance(content, str):
                content = json.dumps(content, cls=DatetimeEncoder)
            async with self.data.session.post(
                    self.data.protocol.config.url(action), data=content
            ) as response:
                resp_json: dict = await response.execute("get_json")

        else:  # MULTIPART
            if isinstance(content, FormData):
                form = content
            elif isinstance(content, dict):
                form = FormData()
                for k, v in content.items():
                    v: Union[str, bytes, Tuple[Any, dict]]
                    if isinstance(v, tuple):
                        form.add_field(k, v[0], **v[1])
                    else:
                        form.add_field(k, v)
            else:
                raise ValueError
            async with self.data.session.post(
                    self.data.protocol.config.url(action), data=form
            ) as response:
                resp_json: dict = await response.execute("get_json")
        if "content" in resp_json:
            resp = resp_json["content"]
        else:
            resp = resp_json

        error_check(resp)
        return resp


class MAHServerDocker(BaseServerDocker[MAHProtocol]):
    prefab_metadata = MAHDockerMeta
    prefab_behavior = MAHBehavior
