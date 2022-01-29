import asyncio
from abc import ABCMeta, abstractmethod
from asyncio import Event
from typing import TYPE_CHECKING, Optional, Union, Type, TypeVar, Dict
from arclet.letoderea.utils import search_event
from .event import EdovesBasicEvent
from .medium import BaseMedium

from ..utilles.security import UNDEFINED, EDOVES_DEFAULT
from ..utilles.data_source_info import DataSourceInfo
from ..utilles import IOStatus
from .exceptions import ValidationFailed, DataMissing
from .typings import TData
from .context import ctx_module

TM = TypeVar("TM", bound=BaseMedium)

if TYPE_CHECKING:
    from .scene import EdovesScene
    from .config import TemplateConfig
    from .interact import InteractiveObject
    from .module import BaseModule
    from .server_docker import BaseServerDocker
    from .monomer import Monomer


class AbstractProtocol(metaclass=ABCMeta):
    scene: "EdovesScene"
    medium: TData
    storage: Dict[Type["InteractiveObject"], "InteractiveObject"]
    __identifier: str = UNDEFINED

    def __init__(self, scene: "EdovesScene", verify_code: str = None):
        self.scene = scene
        if not verify_code and self.__identifier == UNDEFINED:
            raise ValidationFailed
        else:
            self.__identifier = verify_code
        self.storage = {}
        self.medium_ev: Event = asyncio.Event()

    @property
    def identifier(self):
        return self.__identifier

    @property
    def current(self):
        return list(self.storage.values())[-1]

    def verify(self, other: Union[str, "BaseModule"]):
        if isinstance(other, str) and other != self.identifier:
            raise ValidationFailed
        if other.metadata.verify_code == EDOVES_DEFAULT:
            return
        if other.metadata.verify_code != self.identifier:
            other.metadata.state = IOStatus.CLOSED
            raise ValidationFailed

    async def get_medium(
            self,
            event_type: Optional[str] = None,
            medium_type: Optional[Type[TM]] = None
    ) -> Union[TM, TData]:
        if not self.medium_ev.is_set():
            await self.medium_ev.wait()
        self.medium_ev.clear()
        if medium_type and not isinstance(self.medium, medium_type):
            return medium_type().create(self.scene.edoves.self, self.medium, event_type)
        return self.medium

    async def set_medium(self, medium: Union[TM, TData]):
        if self.medium_ev.is_set():
            await self.medium_ev.wait()
        self.medium = medium
        self.medium_ev.set()

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}>"
        )


class ModuleProtocol(AbstractProtocol):
    storage: Dict[Type["BaseModule"], "BaseModule"]
    medium: BaseMedium

    async def broadcast_medium(
            self,
            event_type: Union[str, Type[EdovesBasicEvent]],
            medium_type: Optional[Type[TM]] = None,
            **kwargs
    ):
        evt = event_type.__class__.__name__ if not isinstance(event_type, str) else event_type
        medium = await self.get_medium(evt, medium_type)
        m_list = list(self.storage.values())
        for m in filter(lambda x: x.metadata.state in (IOStatus.ESTABLISHED, IOStatus.MEDIUM_WAIT), m_list):
            with ctx_module.use(m):
                if isinstance(event_type, str):
                    self.scene.edoves.event_system.loop.create_task(
                        m.import_event(search_event(event_type)(medium=medium, **kwargs))
                    )
                else:
                    self.scene.edoves.event_system.loop.create_task(
                        m.import_event(event_type(medium=medium, **kwargs))
                    )


class MonomerProtocol(AbstractProtocol):
    storage: Dict[str, "Monomer"]


class NetworkProtocol(ModuleProtocol):
    storage: Dict[Type["BaseServerDocker"], "BaseServerDocker"]
    source_information: DataSourceInfo
    config: "TemplateConfig"

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "source_information"):
            raise DataMissing
        return super(NetworkProtocol, cls).__new__(cls)

    def __init__(self, scene: "EdovesScene", config: "TemplateConfig"):
        self.config = config
        super().__init__(scene, self.source_information.instance_identifier)

    @abstractmethod
    async def parse_raw_data(self):
        """将server端传入的原始medium处理"""
        raise NotImplementedError

    @abstractmethod
    async def medium_transport(self, action: str):
        """将来自其他模块的medium传出给server"""
        raise NotImplementedError
