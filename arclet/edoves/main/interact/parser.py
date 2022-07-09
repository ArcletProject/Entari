from abc import abstractmethod
from typing import Sequence

from . import InteractiveObject, BaseBehavior, MetadataComponent
from ..medium import BaseMedium
from ..protocol import AbstractProtocol
from ..exceptions import DataMissing


class ParserMetadata(MetadataComponent):
    parser_targets: Sequence[str]
    io: "BaseDataParser"
    __select_type: str

    __limit__ = ["parser_targets", "__select_type", "_ParserMetadata__select_type"]

    def __init__(self, io: "BaseDataParser"):
        super(ParserMetadata, self).__init__(io)
        self.__select_type = "UNKNOWN"
        self.identifier = io.__class__.__name__ + str(
            len(self.parser_targets) + sum([len(t) for t in self.parser_targets])
        )

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
