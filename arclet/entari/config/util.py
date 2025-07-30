from __future__ import annotations

import ast
from dataclasses import Field
import inspect
import sys
from types import MappingProxyType
from typing import Any, cast


def cleanup_src(src: str) -> str:
    lines = src.expandtabs().split("\n")
    margin = len(lines[0]) - len(lines[0].lstrip())
    for i in range(len(lines)):
        lines[i] = lines[i][margin:]
    return "\n".join(lines)


def store_field_description(cls: type, fields: dict[str, Field]) -> None:
    try:
        node: ast.ClassDef = cast(ast.ClassDef, ast.parse(cleanup_src(inspect.getsource(cls))).body[0])
    except (TypeError, OSError):  # NOTE: for REPL.
        return
    for i, stmt in enumerate(node.body):
        name: str | None = None
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            name = stmt.target.id
        if (
            name in fields
            and i + 1 < len(node.body)
            and isinstance((doc_expr := node.body[i + 1]), ast.Expr)
            and isinstance((doc_const := doc_expr.value), ast.Constant)
            and isinstance(doc_string := doc_const.value, str)
            and "description" not in (field := fields[name]).metadata
        ):
            field.metadata = MappingProxyType({**field.metadata.copy(), "description": inspect.cleandoc(doc_string)})


def nest_dict_update(old: dict, new: dict) -> dict:
    """递归更新字典"""
    for k, v in new.items():
        if k not in old:
            old[k] = v
        elif isinstance(v, dict):
            old[k] = nest_dict_update(old[k], v)
        elif isinstance(v, list):
            old[k] = nest_list_update(old[k], v)
        else:
            old[k] = v
    return old


def nest_list_update(old: list, new: list) -> list:
    """递归更新列表"""
    for i, v in enumerate(new):
        if i >= len(old):
            old.append(v)
        elif isinstance(v, dict):
            old[i] = nest_dict_update(old[i], v)
        elif isinstance(v, list):
            old[i] = nest_list_update(old[i], v)
        else:
            old[i] = v
    return old


def nest_obj_update(old, new, attrs: list[str]):
    """递归更新对象"""
    for attr in attrs:
        new_attr = getattr(new, attr)
        if not hasattr(old, attr):
            setattr(old, attr, new_attr)
            continue
        old_attr = getattr(old, attr)
        if not isinstance(new_attr, old_attr.__class__):
            setattr(old, attr, new_attr)
            continue
        if isinstance(new_attr, dict):
            nest_dict_update(old_attr, new_attr)
        elif isinstance(new_attr, list):
            nest_list_update(old_attr, new_attr)
        else:
            setattr(old, attr, new_attr)
    return old


def parent_frame_namespace(*, parent_depth: int = 2, force: bool = False) -> dict[str, Any] | None:
    frame = sys._getframe(parent_depth)
    if force:
        return frame.f_locals

    # if either of the following conditions are true, the class is defined at the top module level
    # to better understand why we need both of these checks, see
    # https://github.com/pydantic/pydantic/pull/10113#discussion_r1714981531
    if frame.f_back is None or frame.f_code.co_name == "<module>":
        return None

    return frame.f_locals


def get_module_ns_of(obj: Any) -> dict[str, Any]:
    module_name = getattr(obj, "__module__", None)
    if module_name:
        try:
            return sys.modules[module_name].__dict__
        except KeyError:
            return {}
    return {}


def merge_cls_and_parent_ns(cls: type[Any], parent_namespace: dict[str, Any] | None = None) -> dict[str, Any]:
    ns = get_module_ns_of(cls).copy()
    if parent_namespace is not None:
        ns.update(parent_namespace)
    ns[cls.__name__] = cls
    return ns
