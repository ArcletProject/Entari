from arclet.alconna import Alconna, command_manager

from ..event import MessageEvent
from ..plugin import Plugin, PluginDispatcher
from .model import Match, Query
from .provider import AlconnaProviderFactory, AlconnaSuppiler, MessageJudger


class AlconnaPluginDispatcher(PluginDispatcher):

    def __init__(
        self,
        plugin: Plugin,
        command: Alconna,
        need_tome: bool = False,
        remove_tome: bool = False,
    ):
        self.supplier = AlconnaSuppiler(command, need_tome, remove_tome)
        super().__init__(plugin, MessageEvent)

        self.bind(MessageJudger(), self.supplier)
        self.bind(AlconnaProviderFactory())

    def dispose(self):
        super().dispose()
        command_manager.delete(self.supplier.cmd)
        del self.supplier.cmd
        del self.supplier

    Match = Match
    Query = Query


def mount(cmd: Alconna, need_tome: bool = False, remove_tome: bool = False):
    if not (plugin := Plugin.current()):
        raise LookupError("no plugin context found")
    disp = AlconnaPluginDispatcher(plugin, cmd, need_tome, remove_tome)
    return disp
