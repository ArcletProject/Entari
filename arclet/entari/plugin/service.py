from typing import TYPE_CHECKING, Any, Callable

from arclet.letoderea import es
from launart import Launart, Service
from launart.status import Phase

from ..event.lifespan import Cleanup, Ready, Startup
from ..logger import log

if TYPE_CHECKING:
    from .model import KeepingVariable, Plugin, RootlessPlugin


class PluginManagerService(Service):
    id = "entari.plugin.manager"

    plugins: dict[str, "Plugin"]
    _keep_values: dict[str, dict[str, "KeepingVariable"]]
    _referents: dict[str, set[str]]
    _unloaded: set[str]
    _subplugined: dict[str, str]
    _apply: dict[str, Callable[[dict[str, Any]], "RootlessPlugin"]]

    def __init__(self):
        super().__init__()
        self.plugins = {}
        self._keep_values = {}
        self._referents = {}
        self._unloaded = set()
        self._subplugined = {}
        self._apply = {}

    @property
    def required(self) -> set[str]:
        return {"entari.service"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "cleanup", "blocking"}

    async def launch(self, manager: Launart):

        for plug in self.plugins.values():
            for serv in plug._services.values():
                manager.add_component(serv)
            plug._load()

        async with self.stage("preparing"):
            await es.publish(Startup())
        async with self.stage("blocking"):
            await es.publish(Ready())
            await manager.status.wait_for_sigexit()
        async with self.stage("cleanup"):
            await es.publish(Cleanup())
            ids = [k for k in self.plugins.keys() if k not in self._subplugined]
            for plug_id in ids:
                plug = self.plugins[plug_id]
                log.plugin.opt(colors=True).debug(f"disposing plugin <y>{plug.id}</y>")
                try:
                    plug.dispose()
                except Exception as e:
                    log.plugin.opt(colors=True).error(f"failed to dispose plugin <y>{plug.id}</y> caused by {e!r}")
                    self.plugins.pop(plug_id, None)
            for values in self._keep_values.values():
                for value in values.values():
                    value.dispose()
                values.clear()
            self._keep_values.clear()


plugin_service = PluginManagerService()
