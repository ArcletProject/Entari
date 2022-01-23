from contextlib import asynccontextmanager
from typing import Union, Dict, Any

from aiohttp import ClientSession, ClientWebSocketResponse
from yarl import URL

from ..main.network import NetworkClient, HTTP_METHODS


class AioHttpClient(NetworkClient):
    session: ClientSession
    ws_conn: ClientWebSocketResponse

    def __init__(self):
        self.session = ClientSession()

    @asynccontextmanager
    async def ensure_network(
            self,
            url: Union[str, URL],
            *,
            method: str = "GET",
            timeout: float = 10.0,
            **kwargs: Any
    ):
        async with self.session.ws_connect(
                url, timeout=timeout, **kwargs
        ) as resp:
            self.ws_conn = resp
            yield resp

    @asynccontextmanager
    async def request(
            self,
            method: "HTTP_METHODS",
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            data: Union[str, bytes] = None,
            **kwargs: Any
    ):
        pass

    @asynccontextmanager
    async def get(
            self,
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        pass

    @asynccontextmanager
    async def post(
            self, url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        pass

    @asynccontextmanager
    async def put(
            self,
            url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        pass

    @asynccontextmanager
    async def delete(
            self,
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        pass

    @asynccontextmanager
    async def patch(
            self,
            url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        pass
