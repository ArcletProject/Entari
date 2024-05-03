from arclet.alconna import Alconna

from ..event import MessageEvent
from ..plugin import Plugin, PluginDispatcher, PluginDispatcherFactory, register_factory
from .provider import AlconnaProviderFactory, AlconnaSuppiler, MessageJudger


class AlconnaDispatcher(PluginDispatcherFactory):

    def __init__(
        self,
        command: Alconna,
        need_tome: bool = False,
        remove_tome: bool = False,
    ):
        self.command = command
        self.need_tome = need_tome
        self.remove_tome = remove_tome

    def dispatch(self, plugin: Plugin) -> PluginDispatcher:
        disp = PluginDispatcher(plugin, MessageEvent)
        disp.bind(MessageJudger(), AlconnaSuppiler(self.command, self.need_tome, self.remove_tome))
        disp.bind(AlconnaProviderFactory())
        return disp


register_factory(
    Alconna,
    lambda cmd, *args, **kwargs: AlconnaDispatcher(cmd, *args, **kwargs),
)
