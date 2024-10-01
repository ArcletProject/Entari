import asyncio
from pathlib import Path
from typing import Union

from launart import Launart, Service, any_completed
from launart.status import Phase
from loguru import logger
from watchfiles import PythonFilter, awatch

from arclet.entari import Plugin, metadata
from arclet.entari.plugin import dispose, find_plugin_by_file, load_plugin

metadata(
    "AutoReload",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="Auto reload plugins when files changed",
)


class Watcher(Service):
    id = "watcher"

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"blocking"}

    def __init__(self, dirs: list[Union[str, Path]]):
        self.dirs = dirs
        super().__init__()

    async def watch(self):
        async for event in awatch(*self.dirs, watch_filter=PythonFilter()):
            for change in event:
                if plugin := find_plugin_by_file(change[1]):
                    logger.info(f"[AutoReload] Detected change in {plugin.id}, reloading...")
                    pid = plugin.id
                    del plugin
                    dispose(pid)
                    if plugin := load_plugin(pid):
                        logger.info(f"[AutoReload] Reloaded {plugin.id}")
                    else:
                        logger.error(f"[AutoReload] Failed to reload {pid}")

    async def launch(self, manager: Launart):
        async with self.stage("blocking"):
            watch_task = asyncio.create_task(self.watch())
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            done, pending = await any_completed(
                sigexit_task,
                watch_task,
            )
            if sigexit_task in done:
                watch_task.cancel()


plug = Plugin.current()
plug.service(Watcher(plug.config.get("watch_dirs", ["."])))
