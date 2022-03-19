from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Union, Type, List, Any, Optional, Dict

from .medium import BaseMedium
from .utilles.security import EDOVES_DEFAULT
from .utilles.data_source_info import DataSourceInfo
from .utilles import IOStatus
from .exceptions import ValidationFailed, DataMissing
from .typings import TData


if TYPE_CHECKING:
    from .screen import Screen
    from .scene import EdovesScene
    from .server_docker import BaseServerDocker
    from .monomer import Monomer
    from .parser import BaseDataParser


class AbstractProtocol(metaclass=ABCMeta):
    parsers: List["BaseDataParser"]
    source_information: DataSourceInfo
    docker: "BaseServerDocker"
    screen: "Screen"

    regular_metas: List[str]
    regular_monomer: Type["Monomer"]

    __scenes: List[str]
    __identifier: str
    __current_scene: "EdovesScene"

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
        if not hasattr(cls, "regular_metas"):
            raise DataMissing(f"{cls.__name__} missing its Regular Metas")
        if not hasattr(cls, "regular_monomer"):
            raise DataMissing(f"{cls.__name__} missing its Regular Monomer")
        return super(AbstractProtocol, cls).__new__(cls)

    def __init__(
            self,
            scene: "EdovesScene",
            verify_code: str = None
    ):
        self.screen = scene.edoves.screen
        self.__scenes = [scene.scene_name]
        self.__current_scene = scene
        self.__identifier = verify_code or self.source_information.instance_identifier

    @property
    def identifier(self):
        return self.__identifier

    @property
    def current_scene(self):
        return self.__current_scene

    @current_scene.setter
    def current_scene(self, scene: "EdovesScene"):
        if scene.scene_name in self.__scenes:
            self.__current_scene = scene
        else:
            raise ValidationFailed(f"Scene:{scene.scene_name} is not accepted by {self.__class__.__name__}")

    def put_scene(self, scene: "EdovesScene"):
        self.__current_scene = scene
        self.__scenes.append(scene.scene_name)

    def verify(self, other: verify_check_list):
        if isinstance(other, str) and other != self.identifier:
            raise ValidationFailed(f"{self.__class__.__name__} verify failed")
        if other.metadata.verify_code == EDOVES_DEFAULT:
            return
        if other.metadata.verify_code != self.identifier:
            other.metadata.state = IOStatus.CLOSED
            raise ValidationFailed(f"{other.__class__.__name__} verify failed")

    def __repr__(self):
        return (
            f"[{self.__class__.__name__}: "
            f"server_docker={self.docker.__class__.__name__}, "
            f"parsers={len(self.parsers)}-parsers"
            f"]"
        )

    async def execution_handle(
            self,
    ) -> Optional[BaseMedium]:
        if self.docker.metadata.state in (IOStatus.CLOSED, IOStatus.CLOSE_WAIT):
            return
        medium = await self.screen.get_medium()
        for p in self.parsers:
            if p.metadata.chosen_parser(medium.type):
                await p.behavior.to_docker(self, medium)

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
        raise NotImplementedError

    @abstractmethod
    def event_type_predicate(self, content: TData) -> str:
        """
        根据api返回原始数据中的event类型字段

        Example:
            return content.get("type")
        """
        raise NotImplementedError

    @abstractmethod
    async def put_metadata(self, meta: str, target: "Monomer", **kwargs):
        """
        请求更新某个monomer的metadata
        """
        raise NotImplementedError

    @abstractmethod
    async def set_metadata(self, meta: str, value: Any, target: "Monomer", **kwargs):
        """
        改变某个monomer的metadata
        """
        raise NotImplementedError

    @abstractmethod
    def include_monomer(self, **kwargs):
        """
        为当前scene添加一个monomer
        """
        raise NotImplementedError

    @abstractmethod
    def exclude_monomer(self, **kwargs):
        """
        为当前scene排除一个monomer
        """
        raise NotImplementedError

    def dispatch_metadata(self, monomer: "Monomer", data: Dict):
        for key, value in data.items():
            if key in self.regular_metas:
                monomer.metadata.__setattr__(key, value)

    # @abstractmethod
    # async def post_message(
    #         self,
    #         ev_type: str,
    #         purveyor: "Monomer",
    #         medium_type: str,
    #         content: List[Dict[str, str]],
    #         **kwargs
    # ):
    #     message = Message().create(purveyor, MessageChain.parse_obj(content), medium_type)
    #     await self.screen.push_medium(message)
    #     await self.screen.broadcast_medium(ev_type, **kwargs)
    #     raise NotImplementedError
    #
    # @abstractmethod
    # async def post_notice(
    #         self,
    #         ev_type: str,
    #         purveyor: "Monomer",
    #         medium_type: str,
    #         content: Dict[str, str],
    #         operator: Optional["Monomer"] = None,
    #         **kwargs
    # ):
    #     notice = Notice().create(purveyor, content, medium_type)
    #     notice.operator = operator
    #     await self.screen.push_medium(notice)
    #     await self.screen.broadcast_medium(ev_type, **kwargs)
    #     raise NotImplementedError
    #
    # @abstractmethod
    # async def post_request(
    #         self,
    #         ev_type: str,
    #         purveyor: "Monomer",
    #         medium_type: str,
    #         content: Dict[str, str],
    #         event_id: str,
    #         **kwargs
    # ):
    #     request = Request().create(purveyor, content, medium_type, event=event_id)
    #     await self.screen.push_medium(request)
    #     await self.screen.broadcast_medium(ev_type, **kwargs)
    #     raise NotImplementedError
