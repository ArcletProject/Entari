from abc import ABCMeta, abstractmethod
from contextlib import asynccontextmanager
from arclet.letoderea.utils import run_always_await
from typing import Union, Any, Literal, Dict, AsyncGenerator, Callable

from yarl import URL

HTTP_METHODS = Union[
    Literal["get"],
    Literal["post"],
    Literal["put"],
    Literal["delete"],
    Literal["patch"],
]


class NetworkResponse:
    activity_handlers: Dict[str, Callable]

    def __init__(
            self,
            **kwargs
    ):
        self.activity_handlers = kwargs

    async def execute(self, target: str):
        handler = self.activity_handlers.get(target)
        if handler is None:
            raise NotImplementedError(f"No handler for exec_func {target}")
        return await run_always_await(handler)


class NetworkClient(metaclass=ABCMeta):

    @abstractmethod
    async def close(self):
        """关闭连接"""

    @abstractmethod
    @asynccontextmanager
    async def ensure_network(
            self,
            url: Union[str, URL],
            *,
            method: str = "GET",
            timeout: float = 10.0,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        raise NotImplementedError

    @abstractmethod
    @asynccontextmanager
    async def request(
            self,
            method: "HTTP_METHODS",
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            data: Union[str, bytes] = None,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        """Perform HTTP request."""
        raise NotImplementedError

    @abstractmethod
    @asynccontextmanager
    async def get(
            self,
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        return await self.request("get", url, headers, **kwargs)

    @abstractmethod
    @asynccontextmanager
    async def post(
            self,
            url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        return await self.request("post", url, headers, data, **kwargs)

    @abstractmethod
    @asynccontextmanager
    async def put(
            self,
            url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        return await self.request("put", url, headers, data, **kwargs)

    @abstractmethod
    @asynccontextmanager
    async def delete(
            self,
            url: Union[str, URL],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        return await self.request("delete", url, headers, **kwargs)

    @abstractmethod
    @asynccontextmanager
    async def patch(
            self,
            url: Union[str, URL],
            data: Union[str, bytes],
            headers: Dict[str, str] = None,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkResponse, None]:
        return await self.request("patch", url, headers, data, **kwargs)
