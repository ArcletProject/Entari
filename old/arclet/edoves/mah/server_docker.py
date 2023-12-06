import asyncio
import json
from asyncio import Event
from typing import Optional, Union, Dict, Any, Tuple, TYPE_CHECKING
from aiohttp import FormData, WSMsgType, WebSocketError
from arclet.edoves.main.interact.server_docker import BaseServerDocker, DockerBehavior, BaseDockerMetaComponent
from arclet.edoves.main.network import NetworkStatus
from arclet.edoves.main.utilles import error_check, DatetimeEncoder, IOStatus
from arclet.edoves.main.utilles.logger import Logger
from arclet.edoves.main.utilles.security import MIRAI_API_HTTP_DEFAULT
from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.builtin.client import AiohttpClient, AiohttpWSConnection
from arclet.edoves.builtin.event.network import DockerOperate


if TYPE_CHECKING:
    from .protocol import MAHProtocol


class MAHDockerMeta(BaseDockerMetaComponent):
    identifier = "edoves.mirai-api-http.docker"
    verify_code: str = MIRAI_API_HTTP_DEFAULT
    client: AiohttpClient
    session_keys: Dict[str, int] = {}


class MAHBehavior(DockerBehavior):
    data: MAHDockerMeta
    conn_ev: Event
    logger: Logger.logger

    async def ws_connection(self) -> Union[AiohttpWSConnection, None]:
        self.logger = self.io.protocol.current_scene.edoves.logger
        retry_count = 0
        while self.data.state in (NetworkStatus.CONNECTING, NetworkStatus.RETRYING):
            if retry_count >= self.io.protocol.current_scene.config.ensure_retries:
                self.logger.warning(f"{self.io.protocol.current_scene.scene_name}: MAHServerDocker connect failed")
                self.io.protocol.current_scene.sig_exit.set()
                return
            try:
                try:
                    return await self.connect()
                except Exception as e:
                    self.logger.warning(f"{self.io.protocol.current_scene.scene_name}: {e}")
                    await self.quit()
                    self.logger.warning(f"{self.io.protocol.current_scene.scene_name}: MAHServerDocker stopped")
                    await asyncio.sleep(5.0)
                    self.logger.info(f"{self.io.protocol.current_scene.scene_name}: MAHServerDocker restarting...")
                    self.data.state = NetworkStatus.RETRYING
                    retry_count += 1
            except asyncio.CancelledError:
                self.data.state = NetworkStatus.DISMISS
                await self.quit()

    async def connect(self):
        self.logger.info(f"{self.io.protocol.current_scene.scene_name}: MAHServerDocker connecting...")
        async with self.data.client.ensure_network(
                self.io.protocol.current_scene.config.url(
                    "all",
                    qq=str(self.io.protocol.current_scene.config.account),
                    verifyKey=str(self.io.protocol.current_scene.config.verify_token)
                )
        ) as resp:
            self.logger.info(f"{self.io.protocol.current_scene.scene_name}: MAHServerDocker connected.")
            self.data.state = NetworkStatus.CONNECTED
            return resp

    def activate(self):
        async def wait_start(operate: DictMedium):
            while not operate.content.get("start"):
                await asyncio.sleep(0.01)
            self.io.protocol.current_scene.edoves.logger.info(
                f"{self.io.protocol.current_scene.scene_name}: MAHServerDocker start!"
            )
            self.data.state = NetworkStatus.CONNECTING
            response = await self.ws_connection()
            self.io.protocol.screen.set_call(operate.mid, response)

        def quit_listen(operate: DictMedium):
            if operate.content.get('stop'):
                self.data.state = IOStatus.CLOSE_WAIT

        self.io.add_handler(DockerOperate, wait_start, quit_listen)

    async def session_fetch(self) -> Optional[DictMedium]:
        ws_conn: AiohttpWSConnection = self.io.protocol.current_scene.protagonist['connect_info']
        try:
            ws_message = await ws_conn.receive(timeout=60.0)
        except asyncio.TimeoutError:
            self.data.state = NetworkStatus.TIMEOUT
            try:
                try:
                    self.logger.debug(f"{self.io.protocol.current_scene.scene_name}: WSConnection trying ping...")
                    await ws_conn.ping()
                    self.data.state = NetworkStatus.CONNECTED
                except Exception as e:
                    self.logger.exception(
                        f"{self.io.protocol.current_scene.scene_name}: WSConnection ping failed: {e!r}"
                    )
                else:
                    return
            except asyncio.CancelledError:
                self.logger.warning(f"{self.io.protocol.current_scene.scene_name}: WSConnection cancelled, stop")
                self.data.state = IOStatus.CLOSE_WAIT
        else:
            if ws_message.type is WSMsgType.TEXT:
                received_data: dict = json.loads(ws_message.data)
                raw_data = received_data['data']
                if 'session' in raw_data:
                    self.data.session_keys[self.io.protocol.current_scene.scene_name] = raw_data['session']
                    self.logger.success(f"{self.io.protocol.current_scene.scene_name}: get session key")
                    await self.io.protocol.ensure_self()
                    return
                try:
                    error_check(raw_data)
                    return DictMedium().create(
                            self.io.protocol.current_scene.protagonist,
                            raw_data,
                            "DataReceived"
                        )
                except Exception as e:
                    self.logger.error(
                        f"{self.io.protocol.current_scene.scene_name}: WSConnection's data has error: {e}"
                    )
            elif ws_message.type is WSMsgType.CLOSE:
                self.logger.warning(f"{self.io.protocol.current_scene.scene_name}: server close WSConnection.")
                self.data.state = IOStatus.CLOSE_WAIT
                return
            elif ws_message.type is WSMsgType.CLOSED:
                self.logger.warning(f"{self.io.protocol.current_scene.scene_name}: WSConnection has been closed.")
                self.data.state = IOStatus.CLOSED
                raise WebSocketError(1, "WSConnection closed.")
            elif ws_message.type is WSMsgType.PONG:
                self.logger.debug(
                    f"{self.io.protocol.current_scene.scene_name}: WSConnection received pong from remote"
                )
            elif ws_message.type == WSMsgType.ERROR:
                self.logger.error(f"{self.io.protocol.current_scene.scene_name}: WSConnection error: {ws_message.data}")
                return
            else:
                self.logger.warning(
                    f"{self.io.protocol.current_scene.scene_name}: "
                    f"WSConnection detected a unknown message type: {ws_message.type}"
                )
                return

    async def quit(self):
        try:
            await self.data.client.close()
            await self.io.protocol.current_scene.protagonist['connect_info'].close()
            self.logger.info(f"{self.io.protocol.current_scene.scene_name}: WSConnection disconnected")
        except TypeError:
            return

    async def session_handle(
            self,
            method: str,
            action: str,
            content: Optional[Union[Dict[str, Any], str, FormData]] = None,
            **kwargs
    ):
        content = content or {}
        if not self.data.client:
            raise RuntimeError(f"{self.io.protocol.current_scene.scene_name}: Unable to get client!")

        if method in {"GET", "get"}:
            if isinstance(content, str):
                content = json.loads(content)
            async with self.data.client.get(
                self.io.protocol.current_scene.config.url(action, **content)
            ) as response:
                resp_json: dict = await response.read_json()

        elif method in {"POST", "Update", "post"}:
            if not isinstance(content, str):
                content = json.dumps(content, cls=DatetimeEncoder)
            async with self.data.client.post(
                    self.io.protocol.current_scene.config.url(action), data=content
            ) as response:
                resp_json: dict = await response.read_json()

        else:  # MULTIPART
            if isinstance(content, FormData):
                form = content
            elif isinstance(content, dict):
                form = FormData(quote_fields=False)
                for k, v in content.items():
                    v: Union[str, bytes, Tuple[Any, dict]]
                    if isinstance(v, tuple):
                        form.add_field(k, v[0], **v[1])
                    else:
                        form.add_field(k, v)
            else:
                raise ValueError
            async with self.data.client.post(
                    self.io.protocol.current_scene.config.url(action), data=form
            ) as response:
                resp_json: dict = await response.read_json()
        resp = resp_json["data"] if "data" in resp_json else resp_json
        error_check(resp_json.get('code'))
        return resp


class MAHServerDocker(BaseServerDocker):
    prefab_metadata = MAHDockerMeta
    prefab_behavior = MAHBehavior
    metadata: MAHDockerMeta
    protocol: "MAHProtocol"

    async def wait_connect(self):
        await self.await_status(NetworkStatus.CONNECTED)
