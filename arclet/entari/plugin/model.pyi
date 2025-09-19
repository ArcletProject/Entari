import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, AsyncGenerator, Awaitable, Generator, Generic, Literal, TypedDict, TypeVar, overload
from typing_extensions import NotRequired, Self

from arclet.letoderea import ExitState, Propagator, Provider, ProviderFactory, Scope, Subscriber
from arclet.letoderea.breakpoint import StepOut
from arclet.letoderea.decorate import _Check
from arclet.letoderea.provider import TProviders
from arclet.letoderea.publisher import Publisher
from arclet.letoderea.scope import _Wrapper
from arclet.letoderea.typing import Resultable, TCallable
from launart import Service
from tarina import ContextModel

current_plugin: ContextModel[Plugin] = ContextModel("_current_plugin")

T = TypeVar("T")
TE = TypeVar("TE", covariant=True)
TE1 = TypeVar("TE1")
TS = TypeVar("TS", bound=Service)
R = TypeVar("R")
R1 = TypeVar("R1")

class PluginDispatcher(Generic[T]):
    publisher: Publisher
    plugin: Plugin
    _event: type
    providers: list[Provider[Any] | ProviderFactory]
    propagators: list[Propagator]

    def __init__(self, plugin: Plugin, event: type, name: str | None = None): ...
    def waiter(
        self, event: Any = None, providers: TProviders | None = None, priority: int = 15, block: bool = False
    ) -> Callable[[Callable[..., R]], StepOut[R]]: ...
    @overload
    def register(
        self,
        func: Callable[..., Generator[T | ExitState | None, None, None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
        once: bool = False,
    ) -> Subscriber[Generator[T, None, None]]: ...
    @overload
    def register(
        self,
        func: Callable[..., AsyncGenerator[T | ExitState | None, None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
        once: bool = False,
    ) -> Subscriber[AsyncGenerator[T, None]]: ...
    @overload
    def register(
        self,
        func: Callable[..., Awaitable[T | ExitState | None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
        once: bool = False,
    ) -> Subscriber[Awaitable[T]]: ...
    @overload
    def register(
        self,
        func: Callable[..., T | ExitState | None],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
        once: bool = False,
    ) -> Subscriber[T]: ...
    @overload
    def register(
        self, *, priority: int = 16, providers: TProviders | None = None, once: bool = False
    ) -> _Wrapper[T]: ...  # noqa: E501
    @overload
    def once(
        self,
        func: Callable[..., Generator[T | ExitState | None, None, None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[Generator[T, None, None]]: ...
    @overload
    def once(
        self,
        func: Callable[..., AsyncGenerator[T | ExitState | None, None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[AsyncGenerator[T, None]]: ...
    @overload
    def once(
        self,
        func: Callable[..., Awaitable[T | ExitState | None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[Awaitable[T]]: ...
    @overload
    def once(
        self, func: Callable[..., T | ExitState | None], *, priority: int = 16, providers: TProviders | None = None
    ) -> Subscriber[T]: ...
    @overload
    def once(self, *, priority: int = 16, providers: TProviders | None = None) -> _Wrapper[T]: ...  # noqa: E501
    on = register
    handle = register
    __call__ = register

class Author(TypedDict):
    name: str
    """作者名称"""
    email: NotRequired[str]
    """作者邮箱"""

class DependService(TypedDict):
    id: str | type[Service]
    """服务名称"""
    stage: NotRequired[Literal["preparing", "prepared", "blocking"]]
    """服务阶段"""

@dataclass
class PluginMetadata:
    name: str
    author: list[str | Author] = ...
    version: str | None = ...
    license: str | None = ...
    urls: dict[str, str] | None = ...
    description: str | None = ...
    icon: str | None = ...
    readme: str | None = ...
    classifier: list[str] = ...
    requirements: list[str] = ...
    depend_services: list[type[Service] | str | DependService] = ...
    config: Any | None = ...

    def get_config_schema(self) -> dict[str, Any]: ...

@overload
def inject(*services: type[Service] | str | DependService) -> Callable[[TCallable], TCallable]: ...
@overload
def inject(*services: type[Service] | str | DependService, _is_global: Literal[True]) -> _Check: ...
@dataclass
class Plugin:
    id: str
    module: ModuleType

    subplugins: set[str] = ...
    config: dict[str, Any] = ...
    is_static: bool = ...
    path: str = ...
    uid: str | None = ...
    _metadata: PluginMetadata | None = ...
    _is_disposed: bool = ...
    _services: dict[str, Service] = field(init=False, default_factory=dict)
    _dispose_callbacks: list[Callable[[], None]] = field(init=False, default_factory=list)
    _config_key: str = field(init=False)
    _scope: Scope = field(init=False)
    _extra: dict[str, Any] = field(default_factory=dict, init=False)  # extra metadata for inspection
    _apply: Callable[[Plugin], Any] | None = field(default=None, init=False)

    @property
    def reusable(self) -> bool: ...
    @property
    def available(self) -> bool: ...
    @staticmethod
    def current() -> Plugin: ...
    @property
    def metadata(self) -> PluginMetadata | None: ...
    @metadata.setter
    def metadata(self, value: PluginMetadata): ...
    def exec_apply(self) -> None: ...
    @property
    def is_available(self) -> bool: ...
    def enable(self) -> set[asyncio.Task] | None: ...
    def disable(self) -> set[asyncio.Task]: ...
    def collect(self, *disposes: Callable[[], None]) -> Self: ...
    def restore(self) -> None: ...
    def dispose(self, *, is_cleanup: bool = False) -> set[asyncio.Task]: ...
    @overload
    def dispatch(self, event: type[Resultable[T]], name: str | None = None) -> PluginDispatcher[T]: ...
    @overload
    def dispatch(self, event: type[Any], name: str | None = None) -> PluginDispatcher[Any]: ...
    @overload
    def use(
        self,
        pub: Publisher[Resultable[T]],
        func: Callable[..., Generator[T | ExitState | None, None, None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[Generator[T, None, None]]: ...
    @overload
    def use(
        self,
        pub: Publisher[Resultable[T]],
        func: Callable[..., AsyncGenerator[T | ExitState | None, None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[AsyncGenerator[T, None]]: ...
    @overload
    def use(
        self,
        pub: Publisher[Resultable[T]],
        func: Callable[..., Awaitable[T | ExitState | None]],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[Awaitable[T]]: ...
    @overload
    def use(
        self,
        pub: Publisher[Resultable[T]],
        func: Callable[..., T | ExitState | None],
        *,
        priority: int = 16,
        providers: TProviders | None = None,
    ) -> Subscriber[T]: ...
    @overload
    def use(
        self, pub: Publisher[Resultable[T]], *, priority: int = 16, providers: TProviders | None = None
    ) -> _Wrapper[T]: ...
    @overload
    def use(
        self, pub: Publisher[Any], func: Callable[..., T], *, priority: int = 16, providers: TProviders | None = None
    ) -> Subscriber[T]: ...
    @overload
    def use(
        self, pub: Publisher[Any], *, priority: int = 16, providers: TProviders | None = None
    ) -> Callable[[Callable[..., T]], Subscriber[T]]: ...
    @overload
    def use(
        self, pub: str, func: Callable[..., T], *, priority: int = 16, providers: TProviders | None = None
    ) -> Subscriber[T]: ...
    @overload
    def use(
        self, pub: str, *, priority: int = 16, providers: TProviders | None = None
    ) -> Callable[[Callable[..., T]], Subscriber[T]]: ...
    def validate(self, func) -> None: ...
    def proxy(self) -> ModuleType: ...
    def subproxy(self, sub_id: str) -> ModuleType: ...
    def service(self, serv: TS | type[TS]) -> TS: ...

class RootlessPlugin(Plugin):
    @classmethod
    @overload
    def apply(
        cls, id: str, *, default: bool = False
    ) -> Callable[[Callable[[RootlessPlugin], Any]], Callable[[], None]]: ...
    @classmethod
    @overload
    def apply(cls, id: str, func: Callable[[RootlessPlugin], Any], *, default: bool = False) -> Callable[[], None]: ...
    def __init__(self, id: str, func: Callable[[RootlessPlugin], Any], config: dict): ...

class KeepingVariable(Generic[T]):
    obj: T
    _dispose: Callable[[T], None] | None
    def __init__(self, obj: T, dispose: Callable[[T], None] | None = None): ...
    def dispose(self): ...

@overload
def keeping(id_: str, obj: T, *, dispose: Callable[[T], None] | None = None) -> T: ...
@overload
def keeping(id_: str, *, obj_factory: Callable[[], T], dispose: Callable[[T], None] | None = None) -> T: ...
