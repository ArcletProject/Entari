from typing import Optional

from arclet.letoderea import make_event


@make_event(name="entari.event/plugin/loaded_success")
class PluginLoadedSuccess:
    name: str


@make_event(name="entari.event/plugin/loaded_failed")
class PluginLoadedFailed:
    name: str
    error: Optional[Exception] = None
    """若没有异常信息，说明该插件加载失败的原因是插件不存在。"""


@make_event(name="entari.event/plugin/unloaded")
class PluginUnloaded:
    name: str
