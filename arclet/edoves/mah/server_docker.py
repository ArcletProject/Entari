import asyncio
import json
from asyncio import Event
from typing import Optional, Union, Dict, Any, Tuple, TYPE_CHECKING
from aiohttp import FormData, WSMsgType
from arclet.edoves.main.server_docker import BaseServerDocker, DockerBehavior, BaseDockerMetaComponent
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
    protocol: "MAHProtocol"
    verify_code: str = MIRAI_API_HTTP_DEFAULT
    session: AiohttpClient
    session_key: str = None


class MAHBehavior(DockerBehavior):
    data: MAHDockerMeta
    ws_conn: AiohttpWSConnection
    start_ev: Event
    conn_ev: Event
    logger: Logger.logger

    def activate(self):
        self.start_ev = Event()

        async def wait_start(operate: MAHDockerMeta.medium_type):
            while not operate.content.get("start"):
                await asyncio.sleep(0.01)
            self.start_ev.set()
            self.data.protocol.scene.edoves.logger.info(
                f"{self.data.protocol.scene.scene_name}: MAHServerDocker start!"
            )
            self.data.state = NetworkStatus.CONNECTING
            while self.data.state != NetworkStatus.CONNECTED:
                await asyncio.sleep(0.01)
            self.data.protocol.set_call(operate.mid, True)

        def quit_listen(operate: MAHDockerMeta.medium_type):
            if operate.content.get('stop'):
                self.data.state = IOStatus.CLOSE_WAIT

        self.io.add_handler(DockerOperate, wait_start, quit_listen)

    async def connect(self):
        self.logger.info(f"{self.data.protocol.scene.scene_name}: MAHServerDocker connecting...")
        async with self.data.session.ensure_network(
                self.data.protocol.config.url(
                    "all",
                    qq=str(self.data.protocol.config.account),
                    verifyKey=str(self.data.protocol.config.verify_token)
                )
        ) as resp:
            self.ws_conn = resp
            self.logger.info(f"{self.data.protocol.scene.scene_name}: MAHServerDocker connected.")
            self.data.state = NetworkStatus.CONNECTED

    async def start(self):
        self.logger = self.data.protocol.scene.edoves.logger
        await self.start_ev.wait()
        retry_count = 0
        while self.data.state in (NetworkStatus.CONNECTING, NetworkStatus.RETRYING):
            if retry_count >= self.data.protocol.scene.config.ensure_retries:
                self.logger.warning(f"{self.data.protocol.scene.scene_name}: MAHServerDocker connect failed")
                raise TimeoutError
            try:
                try:
                    await self.connect()
                except Exception as e:
                    self.logger.warning(f"{self.data.protocol.scene.scene_name}: {e}")
                    await self.quit()
                    self.logger.warning(f"{self.data.protocol.scene.scene_name}: MAHServerDocker stopped")
                    await asyncio.sleep(5.0)
                    self.logger.info(f"{self.data.protocol.scene.scene_name}: MAHServerDocker restarting...")
                    self.data.state = NetworkStatus.RETRYING
                    retry_count += 1
            except asyncio.CancelledError:
                self.data.state = NetworkStatus.DISMISS
                await self.quit()

    async def update(self):
        try:
            ws_message = await self.ws_conn.receive(timeout=60.0)
        except asyncio.TimeoutError:
            self.data.state = NetworkStatus.TIMEOUT
            try:
                try:
                    self.logger.debug(f"{self.data.protocol.scene.scene_name}: WSConnection trying ping...")
                    await self.ws_conn.ping()
                except Exception as e:
                    self.logger.exception(f"{self.data.protocol.scene.scene_name}: WSConnection ping failed: {e!r}")
                else:
                    return
            except asyncio.CancelledError:
                self.logger.warning(f"{self.data.protocol.scene.scene_name}: WSConnection cancelled, stop")
                self.data.state = IOStatus.CLOSE_WAIT
        else:
            if ws_message.type is WSMsgType.TEXT:
                received_data: dict = json.loads(ws_message.data)
                if self.data.session_key:
                    try:
                        error_check(received_data['data'])
                        await self.data.protocol.push_medium(
                            DictMedium().create(
                                self.data.protocol.scene.protagonist,
                                received_data.get('data'),
                                "DataReceived"
                            )
                        )
                        await self.data.protocol.data_parser_dispatch("get")
                    except Exception as e:
                        self.logger.error(
                            f"{self.data.protocol.scene.scene_name}: WSConnection's data has error: {e}"
                        )
                else:
                    if not received_data['syncId']:
                        data = received_data['data']
                        if data['code']:
                            error_check(data)
                        self.data.session_key = data.get("session")
                        await self.data.protocol.ensure_self()
            elif ws_message.type is WSMsgType.CLOSE:
                self.logger.info(f"{self.data.protocol.scene.scene_name}: server close WSConnection.")
                self.data.state = IOStatus.CLOSE_WAIT
                return
            elif ws_message.type is WSMsgType.CLOSED:
                self.logger.info(
                    f"{self.data.protocol.scene.scene_name}: WSConnection has been closed."
                )
                self.data.state = IOStatus.CLOSED
                return
            elif ws_message.type is WSMsgType.PONG:
                self.logger.debug(
                    f"{self.data.protocol.scene.scene_name}: WSConnection received pong from remote"
                )
            elif ws_message.type == WSMsgType.ERROR:
                self.logger.warning(
                    f"{self.data.protocol.scene.scene_name}: WSConnection error: " + ws_message.data
                )
            else:
                self.logger.warning(
                    f"{self.data.protocol.scene.scene_name}: "
                    f"WSConnection detected a unknown message type: {ws_message.type}"
                )

    async def quit(self):
        try:
            await self.ws_conn.close()
            await self.data.session.close()
            self.logger.info(f"{self.data.protocol.scene.scene_name}: WSConnection disconnected")
        except AttributeError:
            return

    async def session_handle(
            self,
            method: str,
            action: str,
            content: Optional[Union[Dict[str, Any], str, FormData]] = None,
            **kwargs
    ):
        content = content or {}
        if not self.data.session:
            raise RuntimeError(f"{self.data.protocol.scene.scene_name}: Unable to get session!")

        if method in ("GET", "get"):
            if isinstance(content, str):
                content = json.loads(content)
            async with self.data.session.get(
                self.data.protocol.config.url(action, **content)
            ) as response:
                resp_json: dict = await response.read_json()

        elif method in ("POST", "Update", "post"):
            if not isinstance(content, str):
                content = json.dumps(content, cls=DatetimeEncoder)
            async with self.data.session.post(
                    self.data.protocol.config.url(action), data=content
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
            async with self.data.session.post(
                    self.data.protocol.config.url(action), data=form
            ) as response:
                resp_json: dict = await response.read_json()
        if "data" in resp_json:
            resp = resp_json["data"]
        else:
            resp = resp_json

        error_check(resp_json.get('code'))
        return resp


class MAHServerDocker(BaseServerDocker):
    prefab_metadata = MAHDockerMeta
    prefab_behavior = MAHBehavior
    metadata: MAHDockerMeta
