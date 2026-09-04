from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .rebase import Fragment, update_schema


@dataclass(frozen=True)
class _FragmentRecord:
    """已注册的 schema 片段"""

    path: tuple[str, ...]
    """规范化后的路径段（空元组 = 整个配置 schema）"""
    fragment: Fragment
    """dict / config 模型类型 / callable"""
    replace: bool
    """True 时目标节点整体替换（跳过深合并）"""
    origin: str | None
    """注册来源插件 id；None = 无插件上下文（仅 dispose 清除会用它）"""


_schema_fragments: dict[str, list[_FragmentRecord]] = {}


def _parse_path(path: str | tuple[str, ...]) -> tuple[str, ...]:
    """把注册 的 path 参数规范化为非空字符串段元组。

    字符串按 `.` 拆段；前导点/连续点/尾随点（空段）一律抛 ValueError

    子插件键以单元素元组 `(".a.b",)` 传入
    """
    if isinstance(path, str):
        if not path:
            return ()
        if path.startswith("."):
            raise ValueError("sub-plugin config keys must be passed as a single-element tuple")
        parts = tuple(path.split("."))
        if any(not part for part in parts):
            raise ValueError(f"invalid schema fragment path {path!r}: empty segment")
        return parts
    parts = tuple(path)
    if any(not isinstance(part, str) or not part for part in parts):
        raise ValueError(f"invalid schema fragment path {path!r}: segments must be non-empty strings")
    return parts


def add_schema_fragment(
    config_key: str,
    path: str | tuple[str, ...] = "",
    fragment: dict | type | Callable[[Any], Any] | None = None,
    replace: bool = False,
    origin: str | None = None,
) -> None:
    """注册一个配置 schema 片段。

    Args:
        config_key (str): 目标插件的配置键。
        path (str | tuple[str, ...]): 点分字符串或段元组；空字符串意味着作用于整个配置 schema。
            以 `.` 开头的子插件键必须用单元素元组，如 `(".a.b",)`。
        fragment: dict（深合并）；config 模型类型（应用时才按最终 ref_root 生成）；
            或 callable（接收目标节点当前值，返回 dict 深合并 / 非 dict 整体替换）。
        replace (bool, optional): 目标节点是否整体替换为片段，不做深合并。默认 False。
        origin (str, optional): 注册来源插件 id；空表示无插件上下文（仅 purge 清除会用它）。默认 None。
    Raises:
        TypeError: fragment 类型不合法
    """

    if fragment is None:
        raise TypeError("schema_fragment requires a `fragment` (dict / config model type / callable)")
    if not isinstance(fragment, dict) and not isinstance(fragment, type) and not callable(fragment):
        raise TypeError(f"unsupported fragment type: {type(fragment).__name__}")
    parts = _parse_path(path)
    records = _schema_fragments.setdefault(config_key, [])
    for record in records:
        if (
            record.origin == origin
            and record.path == parts
            and record.fragment is fragment
            and record.replace == replace
        ):
            return
    records.append(_FragmentRecord(parts, fragment, replace, origin))


def purge_schema_fragments(plugin_id: str) -> None:
    """清除某插件注册的全部 schema 片段"""
    for key in [k for k, v in _schema_fragments.items() if any(r.origin == plugin_id for r in v)]:
        remained = [r for r in _schema_fragments[key] if r.origin != plugin_id]
        if remained:
            _schema_fragments[key] = remained
        else:
            del _schema_fragments[key]


def has_schema_fragments(config_key: str) -> bool:
    return bool(_schema_fragments.get(config_key))


def apply_schema_fragments(schema: dict, config_key: str, ref_root: str = "/") -> dict:
    """按注册顺序把 config_key 的片段应用到 schema（原地合并）并返回 schema。

    单轮应用内对等价片段去重：跨 origin 的重复只生效一次。
    """
    records = _schema_fragments.get(config_key)
    if not records:
        return schema
    applied: list[tuple[tuple[str, ...], bool, Fragment]] = []
    for record in records:
        mark = (record.path, record.replace, record.fragment)
        if any(mark == old for old in applied):
            continue
        applied.append(mark)
        try:
            update_schema(schema, config_key, ref_root, record.path, record.fragment, record.replace)
        except (RuntimeError, ValueError) as e:
            from ...logger import log

            log.plugin.warning(str(e))
    return schema
