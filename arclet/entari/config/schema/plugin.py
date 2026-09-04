from typing import TYPE_CHECKING, Any

from ..action import config_model_schema
from .registry import apply_schema_fragments

if TYPE_CHECKING:
    from arclet.entari.plugin import Plugin


# fmt: off
PLUGIN_META_PROPERTIES = {"$disable": {"type": "string", "description": "Expression for whether disable this plugin"}, "$priority": {"type": "integer", "description": "Plugin loading priority, lower value means higher priority (default: 16)"}, "$filter": {"type": "string", "description": "Plugin filter expression, which will be evaluated in the context of the plugin"}}  # noqa: E501
PLUGIN_META_PROPERTIES_EXTRA = PLUGIN_META_PROPERTIES | {"$optional": {"type": "boolean", "description": "Whether this plugin is optional"}}  # noqa: E501
# fmt: on


def _synthesize_subplugins(plug: "Plugin", schema: dict, ref_root: str):
    from arclet.entari.plugin.service import plugin_service

    properties = schema.setdefault("properties", {})
    if not isinstance(properties, dict):
        # log.warning("plugin schema 'properties' is not a dict, skip sub-plugin synthesis")
        return
    for sid in plug.subplugins:
        if not sid.startswith(plug.id):
            continue
        dotted = sid[len(plug.id) :]
        if (at := dotted.rfind("@")) != -1:  # A.a@uid -> .a（与 module.py:310 加载键一致）
            dotted = dotted[:at]
        meta = {k: dict(v) for k, v in PLUGIN_META_PROPERTIES.items()}
        sub = plugin_service.plugins.get(sid)
        if sub is not None and sub.metadata is not None and sub.metadata.config:
            sub_ref_root = f"{ref_root}properties/{dotted}/"
            sub_schema = config_model_schema(sub.metadata.config, ref_root=sub_ref_root)
            sub_props = sub_schema.setdefault("properties", {})
            if not isinstance(sub_props, dict):
                sub_props = sub_schema["properties"] = {}
            sub_props.update(meta)
            if sub.metadata.description or sub.metadata.name:
                sub_schema.setdefault("description", sub.metadata.description or sub.metadata.name)
            # else:
            #     if sub is not None and sub.metadata is not None:
            #         desc = f"{sub.metadata.description or sub.metadata.name}; no configuration required"
            #     else:
            #         desc = "No configuration required"
            #     sub_schema = {"type": "object", "description": desc, "additionalProperties": True, "properties": meta}
            properties[dotted] = sub_schema


def plugin_config_schema(
    plugin: "Plugin",
    config_key: str | None = None,
    *,
    ref_root: str = "/",
    expand_subplugins: bool = True,
    use_extra_meta: bool = False,
) -> dict[str, Any]:
    """获取插件配置模型的 JSON Schema

    Args:
        plugin (Plugin): 插件实例。
        config_key (str, optional): 插件实例的配置键。
        ref_root (str, optional): JSON Schema $ref 的根路径，默认为 "/"。
        expand_subplugins (bool, optional): 是否展开子插件的配置模型，默认为 True。
        use_extra_meta (bool, optional): 是否使用额外的元属性（$optional），默认为 False。
    """
    meta_properties = {
        k: dict(v) for k, v in (PLUGIN_META_PROPERTIES_EXTRA if use_extra_meta else PLUGIN_META_PROPERTIES).items()
    }
    metadata = plugin.metadata
    if metadata and metadata.config is not None:
        schema = config_model_schema(metadata.config, ref_root=ref_root)
        properties = schema.setdefault("properties", {})
        if not isinstance(properties, dict):
            properties = schema["properties"] = {}
        properties.update(meta_properties)
    elif metadata is not None:
        desc = f"{metadata.description or metadata.name}; no configuration required"
        schema = {"type": "object", "description": desc, "additionalProperties": True, "properties": meta_properties}
    else:
        schema = {
            "type": "object",
            "description": "No configuration required",
            "additionalProperties": True,
            "properties": meta_properties,
        }
    if expand_subplugins:
        _synthesize_subplugins(plugin, schema, ref_root)
    config_key = config_key or getattr(plugin, "_config_key", None)
    if config_key:
        apply_schema_fragments(schema, config_key, ref_root)
    return schema
