from dataclasses import MISSING, Field, asdict, dataclass
from dataclasses import field as _field
from dataclasses import fields, is_dataclass
from inspect import Signature
from typing import Any, Callable, ForwardRef, Optional, TypeVar, get_args, get_origin, overload
from typing_extensions import dataclass_transform

from tarina import generic_isinstance

from ..dc_schema import SchemaGenerator
from ..model import ConfigModelAction
from ..util import merge_cls_and_parent_ns, parent_frame_namespace

_available_dc_attrs = set(Signature.from_callable(dataclass).parameters.keys())
_available_field_attrs = set(Signature.from_callable(Field).parameters.keys())

C = TypeVar("C")
_T = TypeVar("_T")

# fmt: off


@overload
def field(*, default: _T, init: bool = True, repr: bool = True, description: Optional[str] = None, hash: Optional[bool] = None, compare: bool = True, metadata: Optional[dict[str, Any]] = None) -> _T: ...  # noqa: E501


@overload
def field(*, default_factory: Callable[[], _T], init: bool = True, repr: bool = True, description: Optional[str] = None, hash: Optional[bool] = None, compare: bool = True, metadata: Optional[dict[str, Any]] = None) -> _T: ...  # noqa: E501


@overload
def field(*, init: bool = True, repr: bool = True, description: Optional[str] = None, hash: Optional[bool] = None, compare: bool = True, metadata: Optional[dict[str, Any]] = None) -> Any: ...  # noqa: E501


def field(*, default=MISSING, default_factory=MISSING, init=True, repr=True, description=None, hash=None, compare=True, metadata=None):  # noqa: E501  # type: ignore
    if default is not MISSING and default_factory is not MISSING:
        raise ValueError("cannot specify both default and default_factory")
    if metadata is None and description is not None:
        metadata = {"description": description}
    data = {"default": default, "default_factory": default_factory, "init": init, "repr": repr, "hash": hash, "compare": compare, "metadata": metadata, "kw_only": True}  # noqa: E501
    return Field(**{k: v for k, v in data.items() if k in _available_field_attrs})

# fmt: on


@dataclass_transform(kw_only_default=True, field_specifiers=(field, _field))
class BasicConfModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        dataclass(**({k: v for k, v in kwargs.items() if k in _available_dc_attrs} | {"kw_only": True}))(cls)


class BasicConfModelAction(ConfigModelAction[BasicConfModel]):
    # fmt: off
    @classmethod
    def load(cls, data: dict[str, Any], t: type[BasicConfModel]) -> BasicConfModel:
        def _nested_validate(namespace: dict[str, Any], cls_):
            result = {}
            types_namespace = merge_cls_and_parent_ns(cls_, parent_frame_namespace())
            for field_ in fields(cls_):
                if isinstance(field_.type, str):
                    tp = ForwardRef(field_.type, is_argument=True, is_class=True)._evaluate(types_namespace, types_namespace, recursive_guard=frozenset())  # noqa: E501
                else:
                    tp = field_.type
                orig_tp = get_origin(tp)
                if field_.name not in namespace:
                    continue
                if is_dataclass(tp):
                    result[field_.name] = _nested_validate(namespace[field_.name], field_.type)
                elif orig_tp is list and is_dataclass(get_args(tp)[0]):
                    result[field_.name] = [_nested_validate(d, get_args(tp)[0]) for d in namespace[field_.name]]
                elif orig_tp is set and is_dataclass(get_args(tp)[0]):
                    result[field_.name] = {_nested_validate(d, get_args(tp)[0]) for d in namespace[field_.name]}
                elif orig_tp is dict and is_dataclass(get_args(tp)[1]):
                    result[field_.name] = {k: _nested_validate(v, get_args(tp)[1]) for k, v in namespace[field_.name].items()}  # noqa: E501
                elif orig_tp is tuple:
                    args = get_args(tp)
                    result[field_.name] = tuple(_nested_validate(d, args[i]) if is_dataclass(args[i]) else d for i, d in enumerate(namespace[field_.name]))  # noqa: E501
                else:
                    value = namespace[field_.name]
                    if generic_isinstance(value, tp):
                        result[field_.name] = value
            return cls_(**result)

        return _nested_validate(data, t)
    # fmt: on
    @classmethod
    def dump(cls, obj: BasicConfModel) -> dict[str, Any]:
        return asdict(obj)  # type: ignore

    @classmethod
    def keys(cls, obj: BasicConfModel) -> list[str]:
        return [field_.name for field_ in fields(obj)]  # type: ignore

    @classmethod
    def schema(cls, t: type[BasicConfModel]) -> dict[str, Any]:
        return SchemaGenerator(t).create_dc_schema(t)  # type: ignore


__all__ = ["BasicConfModel", "field"]
