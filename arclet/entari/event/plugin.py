from arclet.letoderea import make_event


@make_event(name="entari.event/plugin/loaded_success")
class PluginLoadedSuccess:
    plugin_id: str


@make_event(name="entari.event/plugin/loaded_failed")
class PluginLoadedFailed:
    plugin_id: str
    error: Exception | None = None
    """若没有异常信息，说明该插件加载失败的原因是插件不存在。"""


@make_event(name="entari.event/plugin/unloaded")
class PluginUnloaded:
    plugin_id: str
