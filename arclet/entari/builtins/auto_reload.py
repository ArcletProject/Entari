import asyncio
from pathlib import Path
from typing import Union

from launart import Launart, Service, any_completed
from launart.status import Phase
from watchfiles import PythonFilter, awatch

from arclet.entari import Plugin, dispose_plugin, load_plugin, metadata
from arclet.entari.logger import log
from arclet.entari.plugin import find_plugin_by_file

metadata(
    "AutoReload",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="Auto reload plugins when files changed",
)


logger = log.wrapper("[AutoReload]")


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
        self.fail = {}
        super().__init__()

    async def watch(self):
        async for event in awatch(*self.dirs, watch_filter=PythonFilter()):
            for change in event:
                if plugin := find_plugin_by_file(change[1]):
                    logger("INFO", f"Detected change in {plugin.id}, reloading...")
                    pid = plugin.id
                    del plugin
                    dispose_plugin(pid)
                    if plugin := load_plugin(pid):
                        logger("INFO", f"Reloaded {plugin.id}")
                    else:
                        logger("ERROR", f"Failed to reload {pid}")
                        self.fail[change[1]] = pid
                elif change[1] in self.fail:
                    logger("INFO", f"Detected change in {change[1]} which failed to reload, retrying...")
                    if plugin := load_plugin(self.fail[change[1]]):
                        logger("INFO", f"Reloaded {plugin.id}")
                        del self.fail[change[1]]
                    else:
                        logger("ERROR", f"Failed to reload {self.fail[change[1]]}")

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
        self.fail.clear()


plug = Plugin.current()
plug.service(Watcher(plug.config.get("watch_dirs", ["."])))
