from contextlib import asynccontextmanager
from typing import Union, Dict, Any, Optional
import json
from aiohttp import ClientSession, ClientWebSocketResponse, ClientResponse, WSMessage, FormData
from yarl import URL

from ..main.network import NetworkClient, HTTP_METHODS, NetworkResponse, NetworkConnection


class AiohttpResponse(NetworkResponse):
    response: ClientResponse

    def __init__(self, response: ClientResponse):
        self.response = response

    @property
    def url(self) -> URL:
        return self.response.url

    @property
    def status(self) -> int:
        return self.response.status

    def raise_for_status(self):
        self.response.raise_for_status()

    async def read_json(self) -> dict:
        return await self.response.json()

    async def read(self) -> bytes:
        return await self.response.read()

    async def cookies(self) -> Dict[str, str]:
        return {k: str(v) for k, v in self.response.cookies.items()}

    async def headers(self) -> Dict[str, str]:
        return {k: str(v) for k, v in self.response.headers.items()}

    async def close(self):
        self.response.close()


class AiohttpWSConnection(NetworkConnection):

    async def accept(self) -> None:
        pass

    def status(self) -> int:
        pass

    def raise_for_code(self):
        pass

    response: ClientWebSocketResponse

    def __init__(self, response: ClientWebSocketResponse):
        self.response = response

    async def send(self, data: Union[bytes, str, dict]) -> None:
        if isinstance(data, str):
            return await self.response.send_str(data)
        if isinstance(data, bytes):
            return await self.response.send_bytes(data)
        if isinstance(data, dict):
            return await self.response.send_str(json.dumps(data))

    async def receive(self, timeout: Optional[float] = None) -> WSMessage:
        return await self.response.receive(timeout)

    async def ping(self) -> None:
        return await self.response.ping()

    async def pong(self) -> None:
        return await self.response.pong()

    async def close(self, code: int = 1000, message: bytes = b'') -> None:
        await self.response.close(code=code, message=message)


class AiohttpClient(NetworkClient):
    session: ClientSession

    def __init__(self):
        self.session = ClientSession()

    async def close(self):
        await self.session.close()

    @asynccontextmanager
    async def ensure_network(
            self,
            url: Union[str, URL],
            *,
            method: str = "GET",
            timeout: float = 10.0,
            **kwargs: Any
    ):
        resp: ClientWebSocketResponse = await self.session.ws_connect(url, timeout=timeout, **kwargs).__aenter__()
        yield AiohttpWSConnection(resp)

    @asynccontextmanager
    async def request(
            self,
            method: "HTTP_METHODS",
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            data: Union[str, bytes] = None,
            **kwargs: Any
    ):
        async with self.session.request(
                method, url, **{"headers": headers, "data": data, **kwargs}
        ) as resp:

            yield AiohttpResponse(resp)

    @asynccontextmanager
    async def get(
            self,
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        async with self.session.get(
                url, **{"headers": headers, **kwargs}
        ) as resp:
            yield AiohttpResponse(resp)

    @asynccontextmanager
    async def post(
            self, url: Union[str, URL],
            data: Union[str, bytes, FormData],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        async with self.session.post(
                url, **{"headers": headers, "data": data, **kwargs}
        ) as resp:
            yield AiohttpResponse(resp)

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
