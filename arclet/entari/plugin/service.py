import asyncio
from typing import TYPE_CHECKING

from launart import Launart, Service, any_completed
from launart.status import Phase
from loguru import logger

if TYPE_CHECKING:
    from .model import KeepingVariable, Plugin


class PluginLifecycleService(Service):
    @property
    def id(self) -> str:
        return f"{self.plugin_id}.lifecycle"

    @property
    def required(self) -> set[str]:
        return {"arclet.entari.plugin.manager"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "cleanup", "blocking"}

    def __init__(self, plugin_id: str):
        super().__init__()
        self.plugin_id = plugin_id

    @property
    def available(self) -> bool:
        return bool(plug := plugin_service.plugins.get(self.plugin_id)) and bool(
            plug._preparing or plug._running or plug._cleanup
        )

    @staticmethod
    def iter_preparing(plug: "Plugin"):
        yield from plug._preparing
        for subplug in plug.subplugins:
            yield from PluginLifecycleService.iter_preparing(plugin_service.plugins[subplug])

    @staticmethod
    def iter_cleanup(plug: "Plugin"):
        yield from plug._cleanup
        for subplug in plug.subplugins:
            yield from PluginLifecycleService.iter_cleanup(plugin_service.plugins[subplug])

    @staticmethod
    def iter_running(plug: "Plugin"):
        yield from plug._running
        for subplug in plug.subplugins:
            yield from PluginLifecycleService.iter_running(plugin_service.plugins[subplug])

    async def launch(self, manager: Launart):
        plug = plugin_service.plugins[self.plugin_id]

        async with self.stage("preparing"):
            await asyncio.gather(
                *[func() for func in PluginLifecycleService.iter_preparing(plug)], return_exceptions=True
            )
        async with self.stage("blocking"):
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            running_tasks = [asyncio.create_task(func()) for func in PluginLifecycleService.iter_running(plug)]  # type: ignore
            done, pending = await any_completed(
                sigexit_task,
                *running_tasks,
            )
            if sigexit_task in done:
                for task in pending:
                    task.cancel()
                    await task
        async with self.stage("cleanup"):
            await asyncio.gather(
                *[func() for func in PluginLifecycleService.iter_cleanup(plug)], return_exceptions=True
            )

        del plug


class PluginManagerService(Service):
    id = "arclet.entari.plugin.manager"

    plugins: dict[str, "Plugin"]
    _keep_values: dict[str, dict[str, "KeepingVariable"]]
    _referents: dict[str, set[str]]
    _unloaded: set[str]
    _subplugined: dict[str, str]

    def __init__(self):
        super().__init__()
        self.plugins = {}
        self._keep_values = {}
        self._referents = {}
        self._unloaded = set()
        self._subplugined = {}

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "cleanup", "blocking"}

    async def launch(self, manager: Launart):

        for plug in self.plugins.values():
            if plug._lifecycle and plug._lifecycle.available:
                manager.add_component(plug._lifecycle)
            for serv in plug._services.values():
                manager.add_component(serv)

        async with self.stage("preparing"):
            pass
        async with self.stage("blocking"):
            await manager.status.wait_for_sigexit()
        async with self.stage("cleanup"):
            ids = [k for k in self.plugins.keys() if k not in self._subplugined]
            for plug_id in ids:
                plug = self.plugins[plug_id]
                logger.debug(f"disposing plugin {plug.id}")
                try:
                    plug.dispose()
                except Exception as e:
                    logger.error(f"failed to dispose plugin {plug.id} caused by {e!r}")
                    self.plugins.pop(plug_id, None)
            for values in self._keep_values.values():
                for value in values.values():
                    value.dispose()
                values.clear()
            self._keep_values.clear()


plugin_service = PluginManagerService()
