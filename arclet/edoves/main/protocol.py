from abc import ABCMeta, abstractmethod
from asyncio import PriorityQueue
from typing import TYPE_CHECKING, Optional, Union, Type, TypeVar, Dict, List, Literal, Callable, Any
from .event import EdovesBasicEvent
from .medium import BaseMedium, MediumObserver
from ..builtin.medium import Message, Notice, Request, DictMedium
from .message.chain import MessageChain
from .utilles.security import EDOVES_DEFAULT
from .utilles.data_source_info import DataSourceInfo
from .utilles import IOStatus, MediumStatus
from .exceptions import ValidationFailed, DataMissing
from .typings import TData

TM = TypeVar("TM", bound=BaseMedium)

if TYPE_CHECKING:
    from .scene import EdovesScene
    from .config import TemplateConfig
    from .server_docker import BaseServerDocker
    from .monomer import Monomer
    from .parser import BaseDataParser


class AbstractProtocol(metaclass=ABCMeta):
    scene: "EdovesScene"
    parsers: List["BaseDataParser"]
    docker_type: Type["BaseServerDocker"]
    source_information: DataSourceInfo
    docker: "BaseServerDocker"
    config: "TemplateConfig"
    __medium_call_list: Dict[int, MediumObserver]
    __medium_done_queue: Dict[int, MediumObserver]
    __medium_queue: PriorityQueue
    __identifier: str

    if TYPE_CHECKING:
        from .module import BaseModule
        verify_check_list: Type[Union[str, "BaseModule"]] = Union[str, "BaseModule"]
    else:
        verify_check_list = str

    def __init_subclass__(cls, **kwargs):
        cls.parsers = []
        for base in reversed(cls.__bases__):
            if issubclass(base, AbstractProtocol):
                cls.parsers.extend(getattr(base, "parsers", []))

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "source_information"):
            raise DataMissing(f"{cls.__name__} missing its Source Information")
        if not hasattr(cls, "docker_type"):
            raise DataMissing(f"{cls.__name__} missing its Docker Type")
        return super(AbstractProtocol, cls).__new__(cls)

    def __init__(self, scene: "EdovesScene", config: "TemplateConfig", verify_code: str = None):
        self.scene = scene
        self.__identifier = verify_code or self.source_information.instance_identifier
        self.config = config
        self.__medium_call_list = {}
        self.__medium_done_queue = {}
        self.__medium_queue = PriorityQueue()

    @property
    def identifier(self):
        return self.__identifier

    def verify(self, other: verify_check_list):
        if isinstance(other, str) and other != self.identifier:
            raise ValidationFailed
        if other.metadata.verify_code == EDOVES_DEFAULT:
            return
        if other.metadata.verify_code != self.identifier:
            other.metadata.state = IOStatus.CLOSED
            raise ValidationFailed

    async def get_medium(self, medium_type: Optional[Type[TM]] = None, **kwargs) -> TM:
        medium = await self.__medium_queue.get()
        if medium_type and not isinstance(medium, medium_type):
            medium = medium_type().create(self.scene.protagonist, medium.content, **kwargs)
        self.__medium_done_queue.setdefault(medium.mid, self.__medium_call_list.pop(medium.mid))
        medium.status = MediumStatus.HANDLING
        return medium

    def set_call(self, mid: int, result: Any):
        if mid in self.__medium_done_queue:
            call = self.__medium_done_queue.pop(mid)
            call.set_result(result)

    async def push_medium(
            self,
            medium: Union[TM, TData],
            action: Optional[Callable[[Union[BaseMedium, TData]], TM]] = None,
            in_time: bool = False
    ):
        if isinstance(medium, BaseMedium):
            await self.__medium_queue.put(medium)
            medium.status = MediumStatus.POSTING
            call = MediumObserver(medium, self.scene.edoves.event_system.loop)
            self.__medium_call_list[medium.mid] = call
        elif action:
            medium = action(medium)
            await self.__medium_queue.put(medium)
            medium.status = MediumStatus.POSTING
            call = MediumObserver(medium, self.scene.edoves.event_system.loop)
            self.__medium_call_list[medium.mid] = call
        else:
            raise TypeError
        if in_time:
            await self.broadcast_medium(medium.type)
        return call

    async def broadcast_medium(
            self,
            event_type: Union[str, Type[EdovesBasicEvent]],
            medium_type: Optional[Type[TM]] = None,
            **kwargs
    ):
        evt = event_type.__class__.__name__ if not isinstance(event_type, str) else event_type
        medium = await self.get_medium(medium_type=medium_type, event_type=evt)
        io_list = list(self.scene.all_io.values())
        for io in filter(lambda x: x.metadata.state in (IOStatus.ESTABLISHED, IOStatus.MEDIUM_GET_WAIT), io_list):
            self.scene.edoves.event_system.loop.create_task(
                io.behavior.handler_medium(medium=medium, medium_type=medium_type, event_type=event_type, **kwargs)
            )

    def __repr__(self):
        return (
            f"[{self.__class__.__name__}: "
            f"server_docker={self.docker_type.__name__}, "
            f"parsers={self.parsers}"
            f"]"
        )

    @classmethod
    def register_parser(cls, parser: Type["BaseDataParser"]):
        p = parser()
        cls.parsers.append(p)
        return p

    @abstractmethod
    async def ensure_self(self):
        """
        通过api获取的Bot资料来修改Bot自身的metadata, 主要是name
        """

    @abstractmethod
    def event_type_predicate(self, content: TData) -> str:
        """
        根据api返回原始数据中的event类型字段

        Example:
            return content.get("type")
        """
        raise NotImplementedError

    async def data_parser_dispatch(self, action: Union[Literal["get"], Literal["post"]]):
        if action == "get":
            data = await self.get_medium(DictMedium)
            for p in self.parsers:
                if p.metadata.chosen_parser(self.event_type_predicate(data.content)):
                    await p.behavior.from_docker(self, data)

        elif action == "post":
            if self.docker.metadata.state in (IOStatus.CLOSED, IOStatus.CLOSE_WAIT):
                return
            medium = await self.get_medium(DictMedium)
            for p in self.parsers:
                if p.metadata.chosen_parser(medium.type):
                    await p.behavior.to_docker(self, medium)

    @abstractmethod
    async def post_message(
            self,
            ev_type: str,
            purveyor: "Monomer",
            medium_type: str,
            content: List[Dict[str, str]],
            **kwargs
    ):
        message = Message().create(purveyor, MessageChain.parse_obj(content), medium_type)
        await self.push_medium(message)
        await self.broadcast_medium(ev_type, **kwargs)
        raise NotImplementedError

    @abstractmethod
    async def post_notice(
            self,
            ev_type: str,
            purveyor: "Monomer",
            medium_type: str,
            content: Dict[str, str],
            operator: Optional["Monomer"] = None,
            **kwargs
    ):
        notice = Notice().create(purveyor, content, medium_type)
        notice.operator = operator
        await self.push_medium(notice)
        await self.broadcast_medium(ev_type, **kwargs)
        raise NotImplementedError

    @abstractmethod
    async def post_request(
            self,
            ev_type: str,
            purveyor: "Monomer",
            medium_type: str,
            content: Dict[str, str],
            event_id: str,
            **kwargs
    ):
        request = Request().create(purveyor, content, medium_type, event=event_id)
        await self.push_medium(request)
        await self.broadcast_medium(ev_type, **kwargs)
        raise NotImplementedError
