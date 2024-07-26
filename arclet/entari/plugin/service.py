import asyncio
from typing import TYPE_CHECKING

from launart import Launart, Service
from launart.status import Phase
from loguru import logger

if TYPE_CHECKING:
    from .model import Plugin


class PluginService(Service):
    id = "arclet.entari.plugin_service"

    plugins: dict[str, "Plugin"]

    def __init__(self):
        super().__init__()
        self.plugins = {}

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "cleanup"}

    async def launch(self, manager: Launart):
        _preparing = []
        _cleanup = []
        async with self.stage("preparing"):
            for plug in self.plugins.values():
                _preparing.extend([func() for func in plug._preparing])
            await asyncio.gather(*_preparing, return_exceptions=True)
        async with self.stage("cleanup"):
            for plug in self.plugins.values():
                _cleanup.extend([func() for func in plug._cleanup])
            await asyncio.gather(*_cleanup, return_exceptions=True)
        ids = [*self.plugins.keys()]
        for plug_id in ids:
            plug = self.plugins[plug_id]
            logger.debug(f"disposing plugin {plug.id}")
            try:
                plug.dispose()
            except Exception as e:
                logger.error(f"failed to dispose plugin {plug.id} caused by {e!r}")
                self.plugins.pop(plug_id, None)


service = PluginService()
