from enum import Enum
from typing import Union, TYPE_CHECKING, Type, Generator, TypeVar
from pydantic import BaseModel, BaseConfig, Extra

if TYPE_CHECKING:
    from pydantic.typing import AbstractSetIntStr, DictStrAny, MappingIntStrAny

T = TypeVar("T")


def gen_subclass(target: Type[T]) -> Generator[Type[T], None, None]:
    yield target
    for sub_cls in target.__subclasses__():
        yield from gen_subclass(sub_cls)


class DataStructure(BaseModel):
    """
    一切数据模型的基类.
    """

    def dict(
            self,
            *,
            include: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
            exclude: Union["AbstractSetIntStr", "MappingIntStrAny"] = None,
            by_alias: bool = False,
            skip_defaults: bool = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
    ) -> "DictStrAny":
        return super().dict(
            include=include,
            exclude=exclude,
            by_alias=True,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=True,
        )

    class Config(BaseConfig):
        extra = Extra.allow


class MetasChecker(type):
    __metas__ = {}

    def __init__(cls, name, bases, dic):
        super().__init__(name, bases, dic)
        cls.__metas__.update(dic['__annotations__'])

    def __call__(cls, *args, **kwargs):
        print(cls.__metas__)
        print(getattr(cls, '__metadata__'))
        print(cls.__mro__)
        obj = cls.__new__(cls, *args, **kwargs)
        cls.__init__(cls, *args, **kwargs)
        return obj


class ModuleStatus(int, Enum):
    """描述模块的状态"""

    """等待激活"""
    ACTIVATE_WAIT = 411831

    """激活成功, 可以接受medium"""
    ESTABLISHED = 26366521

    """请求app端发送medium"""
    MEDIUM_WAIT = 2452720

    """正在处理medium"""
    PROCESSING = 5572535

    """请求app端卸载该模块"""
    CLOSE_WAIT = 3078491

    """该模块已关闭"""
    CLOSED = 17080094

    """未知状态"""
    UNKNOWN = 17156595


class MonomerStatus(int, Enum):
    """描述单体的状态"""

    ENABLE = 1
    DISABLE = 2
    DESTROYED = 3
