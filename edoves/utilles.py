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


class ModuleStatus(Enum):
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


import builtins


class _MISSING:
    pass


MISSING = _MISSING()


def _create_fn(name, args, body, *, globals=None, locals=None,
               return_type=MISSING):
    # Note that we mutate locals when exec() is called.  Caller
    # beware!  The only callers are internal to this module, so no
    # worries about external callers.
    if locals is None:
        locals = {}
    if 'BUILTINS' not in locals:
        locals['BUILTINS'] = builtins
    return_annotation = ''
    if return_type is not MISSING:
        locals['_return_type'] = return_type
        return_annotation = '->_return_type'
    args = ','.join(args)
    body = '\n'.join(f'  {b}' for b in body)

    # Compute the text of the entire function.
    txt = f' def {name}({args}){return_annotation}:\n{body}'

    local_vars = ', '.join(locals.keys())
    txt = f"def __create_fn__({local_vars}):\n{txt}\n return {name}"
    print(txt)
    ns = {}
    exec(txt, globals, ns)
    return ns['__create_fn__'](**locals)


def _create_init(cls):
    print(cls.__dict__)
    metadata = getattr(cls, "__metadata__", None)
    if metadata:
        local = {'BUILTINS': builtins}
        metas = []
        for meta in metadata:
            metas.append(f'{f.name}:_type_{f.name}{default}')

        args = ','.join(metas)
        body = '\n'.join(f'  {b}' for b in body)

        # Compute the text of the entire function.
        txt = f' def __init__({args}):\n{body}'

        local_vars = ', '.join(local.keys())
        txt = f"def __create_fn__({local_vars}):\n{txt}\n return __init__"
        print(txt)
        ns = {}
        exec(txt, {}, ns)
        return ns['__create_fn__'](**local)


def micro_class(cls=None, /, *, init=True, repr=True, eq=True):
    def wrap(cls):
        setattr(cls, "__init__", _create_fn(name="__init__", args=["self", "a: int"], body=["pass"]))
        print(cls.__dict__)
        return cls

    if cls is None:
        return wrap

    return wrap(cls)
