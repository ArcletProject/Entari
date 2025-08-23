from dataclasses import MISSING, Field, asdict, dataclass
from dataclasses import field as _field
from dataclasses import fields, is_dataclass
from inspect import Signature
from typing import Any, Callable, ForwardRef, Optional, TypeVar, get_args, overload
from typing_extensions import dataclass_transform

from tarina import generic_isinstance
from tarina.generic import get_origin, origin_is_union
from tarina.signature import merge_cls_and_parent_ns

from ..dc_schema import SchemaGenerator
from ..model import ConfigModelAction

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
        dataclass(**({k: v for k, v in (kwargs | {"kw_only": True}).items() if k in _available_dc_attrs}))(cls)


def _resolve_type(field_type: Any, types_namespace: dict[str, Any]) -> Any:
    """解析字段类型，处理字符串类型引用"""
    if isinstance(field_type, str):
        return ForwardRef(field_type, is_argument=True, is_class=True)._evaluate(
            types_namespace, types_namespace, recursive_guard=frozenset()
        )
    return field_type


def _validate_union_type(value: Any, union_type: Any) -> tuple[bool, Any]:
    """验证 Union 类型，返回 (是否成功, 验证后的值)"""
    args = get_args(union_type)
    non_none_args = tuple(tp for tp in args if tp is not type(None))

    # 如果值为 None 且 Union 包含 NoneType，则直接返回
    if value is None and type(None) in args:
        return True, None

    for arg_type in non_none_args:
        try:
            if is_dataclass(arg_type):
                if isinstance(value, dict):
                    validated_value = _nested_validate(value, arg_type)
                    return True, validated_value
                elif generic_isinstance(value, arg_type):
                    return True, value
            elif generic_isinstance(value, arg_type):
                return True, value
            else:
                validated_value = _validate_complex_type(value, arg_type)
                if validated_value is not None:
                    return True, validated_value
        except (TypeError, ValueError, AttributeError):
            continue

    return False, value


def _validate_complex_type(value: Any, tp: Any) -> Any:
    """验证复杂类型（list, dict, set, tuple 等）"""
    orig_tp = get_origin(tp)

    if orig_tp is list and isinstance(value, list):
        args = get_args(tp)
        if args and is_dataclass(args[0]):
            return [_nested_validate(d, args[0]) for d in value]
        elif args:
            return [_validate_single_value(d, args[0]) for d in value]
        return value

    elif orig_tp is set and isinstance(value, (set, list)):
        args = get_args(tp)
        if args and is_dataclass(args[0]):
            return {_nested_validate(d, args[0]) for d in value}
        elif args:
            return {_validate_single_value(d, args[0]) for d in value}
        return set(value) if isinstance(value, list) else value

    elif orig_tp is dict and isinstance(value, dict):
        args = get_args(tp)
        if len(args) >= 2 and is_dataclass(args[1]):
            return {k: _nested_validate(v, args[1]) for k, v in value.items()}
        elif len(args) >= 2:
            return {k: _validate_single_value(v, args[1]) for k, v in value.items()}
        return value

    elif orig_tp is tuple and isinstance(value, (tuple, list)):
        args = get_args(tp)
        if args:
            result = []
            for i, item in enumerate(value):
                if i < len(args):
                    if is_dataclass(args[i]):
                        result.append(_nested_validate(item, args[i]))
                    else:
                        result.append(_validate_single_value(item, args[i]))
                else:
                    result.append(item)
            return tuple(result)
        return tuple(value) if isinstance(value, list) else value

    return None


def _validate_single_value(value: Any, tp: Any) -> Any:
    """验证单个值"""
    if origin_is_union(get_origin(tp)):
        success, validated = _validate_union_type(value, tp)
        return validated if success else value
    elif is_dataclass(tp):
        if isinstance(value, dict):
            return _nested_validate(value, tp)
        return value
    elif generic_isinstance(value, tp):
        return value
    else:
        validated = _validate_complex_type(value, tp)
        return validated if validated is not None else value


def _nested_validate(namespace: dict[str, Any], cls_):
    """递归验证嵌套的数据类"""
    result = {}
    types_namespace = merge_cls_and_parent_ns(cls_)

    for field_ in fields(cls_):
        if field_.name not in namespace:
            continue

        tp = _resolve_type(field_.type, types_namespace)
        field_.type = tp
        value = namespace[field_.name]

        if origin_is_union(get_origin(tp)):
            success, validated_value = _validate_union_type(value, tp)
            if success:
                result[field_.name] = validated_value
            continue

        validated_value = _validate_single_value(value, tp)
        result[field_.name] = validated_value

    return cls_(**result)


class BasicConfModelAction(ConfigModelAction[BasicConfModel]):
    # fmt: off
    @classmethod
    def load(cls, data: dict[str, Any], t: type[BasicConfModel]) -> BasicConfModel:
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
