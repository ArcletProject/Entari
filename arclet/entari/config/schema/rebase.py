import copy
from collections.abc import Callable
from typing import Any, TypeAlias

from ..action import config_model_schema

_SENTINEL = object()

Fragment: TypeAlias = dict[str, Any] | type | Callable[[Any], Any]


def _deep_merge(target: dict, source: dict) -> None:
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def _pointer_path(parts: tuple[str, ...]) -> str:
    """拼接 JSON Pointer 风格的路径字符串（用于 schema 的 $ref）"""
    segments: list[str] = []
    for part in parts:
        if part.startswith("."):
            segments.append("properties")
        segments.append(part)
    return "/" + "/".join(segments) if segments else ""


def _resolve_target(schema: dict, parts: tuple[str, ...]) -> tuple[dict | None, str | None, dict | None]:
    """沿 parts 在 schema 内导航到目标节点，返回 (holder, key, target)
    - target: 已存在的 dict 目标节点（可原地深合并）；
    - target 为 None 且 holder/key 非空：目标缺失或为非 dict，调用方应整体写入 holder[key]；
    - holder 为 None：导航中途遇到已存在但非 dict 的节点，已告警，调用方跳过该片段。

    Raises:
        ValueError: 导航中途遇到已存在但非 dict 的节点
    """
    node: Any = schema
    holder: dict | None = None
    key: str | None = None
    last = len(parts) - 1
    if not parts:
        return schema, None, schema  # 空 path：目标即 schema 根
    for index, part in enumerate(parts):
        if part.startswith("."):
            if not isinstance(node, dict):
                raise ValueError(f"schema fragment path crosses non-dict node {part!r}, skipped")
            props = node.setdefault("properties", {})
            if not isinstance(props, dict):
                raise ValueError("schema fragment path crosses non-dict 'properties' node, skipped")
            holder, key = props, part
            value = props.get(part, _SENTINEL)
        else:
            if not isinstance(node, dict):
                raise ValueError(f"schema fragment path crosses non-dict node {part!r}, skipped")
            holder, key = node, part
            value = node.get(part, _SENTINEL)
        if index == last:
            if isinstance(value, dict):
                return holder, key, value
            return holder, key, None
        if isinstance(value, dict):
            node = value
        elif value is _SENTINEL:
            node = holder[key] = {"type": "object"}
        else:
            raise ValueError(f"schema fragment path crosses existing non-dict node {part!r}, skipped")
    return holder, key, None


def _rewrite_refs(node: Any, renamed: dict[str, str], model_prefix: str, ref_root: str) -> None:
    """把片段内 $ref 就地重写为提升后的位置。

    匹配两种源形态（其余前缀视为指向片段外，保持原样并告警）：
    - `#{最终 ref_root}$defs/X`：模型片段生成时带完整前缀；
    - `#/$defs/X`：手写 dict 片段相对片段根的形式。
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            name: str | None = None
            if ref.startswith(model_prefix):
                name = ref[len(model_prefix) :]
            elif ref.startswith("#/$defs/"):
                name = ref[len("#/$defs/") :]
            if name is not None:
                if name in renamed:
                    node["$ref"] = f"#{ref_root}$defs/{renamed[name]}"
                else:
                    # log.warning(f"schema fragment $ref {ref!r} points to unknown local $defs {name!r}, kept as-is")
                    pass
        for value in node.values():
            _rewrite_refs(value, renamed, model_prefix, ref_root)
    elif isinstance(node, list):
        for item in node:
            _rewrite_refs(item, renamed, model_prefix, ref_root)


def _collect_defs_and_rebase(
    content: dict, *, config_key: str, parts: tuple[str, ...], ref_root: str, final_ref_root: str
) -> dict[str, dict]:
    """提取片段根级 $defs，唯一化重命名并就地重写 content 内 $ref。

    返回 {新名: defs schema 深拷贝}。
    """
    defs = content.pop("$defs", None)
    if not isinstance(defs, dict) or not defs:
        return {}
    path_token = ".".join(parts).strip(".") or "root"
    renamed: dict[str, str] = {}
    hoisted: dict[str, dict] = {}
    for name, def_schema in defs.items():
        new_name = f"{config_key}.{path_token}.{name}"
        renamed[name] = new_name
        hoisted[new_name] = copy.deepcopy(def_schema)
    _rewrite_refs(content, renamed, f"#{final_ref_root}$defs/", ref_root)
    return hoisted


def update_schema(
    schema: dict, config_key: str, ref_root: str, parts: tuple[str, ...], payload: Fragment, replace: bool = False
) -> None:
    final_ref_root = f"{ref_root}{_pointer_path(parts)}/" if parts else ref_root
    if isinstance(payload, type):
        # 模型片段：以最终 ref_root 生成，再走统一的 defs 处理
        try:
            payload = config_model_schema(payload, ref_root=final_ref_root)
        except Exception as e:
            raise RuntimeError(f"failed to resolve config model fragment {payload!r}: {e!r}, skipped") from e
    holder, key, target = _resolve_target(schema, parts)
    if holder is None:
        return
    if callable(payload) and not isinstance(payload, type):
        try:
            current = copy.deepcopy(target) if target is not None else None
            payload = payload(current)
        except Exception as e:
            raise RuntimeError(f"schema fragment callable raised {e!r}, skipped") from e
    if not isinstance(payload, dict):
        holder[key] = copy.deepcopy(payload)
        return
    content = copy.deepcopy(payload)  # 绝不原地改写注册的片段：热重载后再次应用时内容必须仍是原样
    hoisted = _collect_defs_and_rebase(
        content, config_key=config_key, parts=parts, ref_root=ref_root, final_ref_root=final_ref_root
    )  # 先剥离 content 的 $defs 并重写 ref，再合并，避免原样 defs 先落入目标
    if target is not None and not replace:
        _deep_merge(target, content)
    elif target is not None:
        target.clear()  # replace 空 path：整体替换基础 schema
        _deep_merge(target, content)
    else:
        holder[key] = content
    # replace 空 path 会清空 schema 根，不能被 clear 冲掉
    if hoisted:
        schema.setdefault("$defs", {}).update(hoisted)
