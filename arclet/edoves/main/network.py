from abc import ABCMeta, abstractmethod
from contextlib import asynccontextmanager
from typing import Union, Any, Literal, Dict, AsyncGenerator

from yarl import URL

HTTP_METHODS = Union[
    Literal["get"],
    Literal["post"],
    Literal["put"],
    Literal["delete"],
    Literal["patch"],
]


class NetworkResponse(metaclass=ABCMeta):
    url: URL

    @abstractmethod
    async def read(self) -> bytes:
        ...

    @abstractmethod
    async def cookies(self) -> Dict[str, str]:
        ...

    @abstractmethod
    async def headers(self) -> Dict[str, str]:
        ...

    @abstractmethod
    async def close(self):
        ...

    @property
    @abstractmethod
    def status(self) -> int:
        ...

    @abstractmethod
    def raise_for_status(self):
        ...


class NetworkConnection(metaclass=ABCMeta):
    server_mode: bool

    @abstractmethod
    async def accept(self) -> None:
        pass

    @abstractmethod
    async def send(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def receive(self) -> bytes:
        ...

    @abstractmethod
    async def ping(self) -> None:
        ...

    @abstractmethod
    async def pong(self) -> None:
        ...

    @abstractmethod
    async def close(self, code: int = 1000, message: bytes = b'') -> None:
        ...

    @abstractmethod
    def status(self) -> int:
        ...

    @abstractmethod
    def raise_for_code(self):
        ...


class NetworkClient(metaclass=ABCMeta):

    @abstractmethod
    async def close(self):
        """关闭可能存在的连接"""

    @abstractmethod
    @asynccontextmanager
    async def ensure_network(
            self,
            url: Union[str, URL],
            *,
            method: str = "GET",
            timeout: float = 10.0,
            **kwargs: Any
    ) -> AsyncGenerator[NetworkConnection, None]:
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
