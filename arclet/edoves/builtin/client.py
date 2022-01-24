from contextlib import asynccontextmanager
from typing import Union, Dict, Any

from aiohttp import ClientSession, ClientWebSocketResponse
from yarl import URL

from ..main.network import NetworkClient, HTTP_METHODS, NetworkResponse


class AioHttpClient(NetworkClient):
    session: ClientSession

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
        # async with self.session.ws_connect(
        #         url, timeout=timeout, **kwargs
        # ) as resp:
        #     yield NetworkResponse(get_connection=lambda: resp)
        resp = await self.session.ws_connect(url, timeout=timeout, **kwargs).__aenter__()
        yield NetworkResponse(get_connection=lambda: resp)

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
            async def _read():
                return await resp.read()

            yield NetworkResponse(get_content=_read)

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
            resp.raise_for_status()

            async def _read():
                return await resp.read()

            async def _json():
                return await resp.json()

            yield NetworkResponse(get_content=_read, get_json=_json)

    @asynccontextmanager
    async def post(
            self, url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ):
        async with self.session.post(
                url, **{"headers": headers, "data": data, **kwargs}
        ) as resp:
            resp.raise_for_status()

            async def _read():
                return await resp.read()

            async def _json():
                return await resp.json()

            yield NetworkResponse(get_content=_read, get_json=_json)

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
