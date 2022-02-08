from abc import abstractmethod
from typing import Iterable
from .medium import BaseMedium
from .interact import InteractiveObject, BaseBehavior, MetadataComponent
from .protocol import AbstractProtocol
from .exceptions import DataMissing


class ParserMetadata(MetadataComponent):
    parser_targets: Iterable[str]
    io: "BaseDataParser"
    __select_type: str

    def __init__(self, io: "BaseDataParser"):
        super(ParserMetadata, self).__init__(io)
        self.__select_type = "UNKNOWN"

    @property
    def select_type(self):
        return self.io.metadata.__select_type

    def chosen_parser(self, target: str):
        for p in self.parser_targets:
            if p == target:
                self.__select_type = p
                return p

    def __new__(cls, *args, **kwargs):
        if not getattr(cls, "parser_targets", None):
            raise DataMissing(f"{cls.__name__} is missing parser_targets")
        return super().__new__(cls)


class ParserBehavior(BaseBehavior):
    io: "BaseDataParser"

    def activate(self):
        pass

    @abstractmethod
    async def from_docker(self, protocol: AbstractProtocol, data: BaseMedium):
        """将server端传入的原始medium处理"""
        pass

    @abstractmethod
    async def to_docker(self, protocol: AbstractProtocol, data: BaseMedium):
        """将来自其他模块的medium传出给server"""
        pass


class BaseDataParser(InteractiveObject):
    prefab_metadata = ParserMetadata
    prefab_behavior = ParserBehavior
    metadata: ParserMetadata
    behavior: prefab_behavior

    def __repr__(self):
        return f"<{self.__class__.__name__}>"
