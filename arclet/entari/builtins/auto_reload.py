import asyncio
from pathlib import Path
from typing import Union

from arclet.letoderea import es
from launart import Launart, Service, any_completed
from launart.status import Phase
from watchfiles import PythonFilter, awatch

from arclet.entari import Plugin, dispose_plugin, load_plugin, metadata
from arclet.entari.config import EntariConfig
from arclet.entari.event.config import ConfigReload
from arclet.entari.logger import log
from arclet.entari.plugin import find_plugin, find_plugin_by_file

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

    def __init__(self, dirs: list[Union[str, Path]], is_watch_config: bool):
        self.dirs = dirs
        self.is_watch_config = is_watch_config
        self.fail = {}
        super().__init__()

    async def watch(self):
        async for event in awatch(*self.dirs, watch_filter=PythonFilter()):
            for change in event:
                if plugin := find_plugin_by_file(change[1]):
                    if plugin.id == "arclet.entari.builtins.auto_reload":
                        logger("DEBUG", f"Detected change in <blue>{plugin.id!r}</blue>, ignored")
                        continue
                    logger("INFO", f"Detected change in <blue>{plugin.id!r}</blue>, reloading...")
                    await plugin._cleanup()
                    pid = plugin.id
                    del plugin
                    dispose_plugin(pid)
                    if plugin := load_plugin(pid):
                        logger("INFO", f"Reloaded <blue>{plugin.id!r}</blue>")
                        plugin._load()
                        await plugin._startup()
                        await plugin._ready()
                        del plugin
                    else:
                        logger("ERROR", f"Failed to reload <blue>{pid!r}</blue>")
                        self.fail[change[1]] = pid
                elif change[1] in self.fail:
                    logger("INFO", f"Detected change in {change[1]!r} which failed to reload, retrying...")
                    if plugin := load_plugin(self.fail[change[1]]):
                        logger("INFO", f"Reloaded <blue>{plugin.id!r}</blue>")
                        plugin._load()
                        await plugin._startup()
                        await plugin._ready()
                        del plugin
                        del self.fail[change[1]]
                    else:
                        logger("ERROR", f"Failed to reload <blue>{self.fail[change[1]]!r}</blue>")

    async def watch_config(self):
        file = EntariConfig.instance.path
        async for event in awatch(file.resolve().absolute().parent, recursive=False):
            for change in event:
                if change[0].name != "modified":
                    continue
                if Path(change[1]).resolve().name != file.name:
                    continue
                if not self.is_watch_config:
                    continue
                logger("INFO", f"Detected change in {str(file)!r}, reloading config...")

                old_basic = EntariConfig.instance.basic.copy()
                old_plugin = EntariConfig.instance.plugin.copy()
                EntariConfig.instance.reload()
                for key in old_basic:
                    if key in EntariConfig.instance.basic and old_basic[key] != EntariConfig.instance.basic[key]:
                        logger(
                            "DEBUG",
                            f"Basic config <y>{key!r}</y> changed from <r>{old_basic[key]!r}</r> "
                            f"to <g>{EntariConfig.instance.basic[key]!r}</g>",
                        )
                        await es.publish(ConfigReload("basic", key, EntariConfig.instance.basic[key]))
                for plugin_name in old_plugin:
                    pid = plugin_name.replace("::", "arclet.entari.builtins.")
                    if (
                        plugin_name not in EntariConfig.instance.plugin
                        or EntariConfig.instance.plugin[plugin_name] is False
                    ) and (plugin := find_plugin(pid)):
                        await plugin._cleanup()
                        del plugin
                        dispose_plugin(pid)
                        logger("INFO", f"Disposed plugin <blue>{pid!r}</blue>")
                        continue
                    if old_plugin[plugin_name] != EntariConfig.instance.plugin[plugin_name]:
                        logger(
                            "DEBUG",
                            f"Plugin <y>{plugin_name!r}</y> config changed from <r>{old_plugin[plugin_name]!r}</r> "
                            f"to <g>{EntariConfig.instance.plugin[plugin_name]!r}</g>",
                        )
                        res = await es.post(
                            ConfigReload("plugin", plugin_name, EntariConfig.instance.plugin[plugin_name])
                        )
                        if res and res.value:
                            logger("DEBUG", f"Plugin <y>{pid!r}</y> config change handled by itself.")
                            continue
                        if plugin := find_plugin(pid):
                            logger("INFO", f"Detected <blue>{pid!r}</blue>'s config change, reloading...")
                            plugin_file = str(plugin.module.__file__)
                            await plugin._cleanup()
                            dispose_plugin(plugin_name)
                            if plugin := load_plugin(plugin_name):
                                plugin._load()
                                await plugin._startup()
                                await plugin._ready()
                                logger("INFO", f"Reloaded <blue>{plugin.id!r}</blue>")
                                del plugin
                            else:
                                logger("ERROR", f"Failed to reload <blue>{plugin_name!r}</blue>")
                                self.fail[plugin_file] = pid
                        else:
                            logger("INFO", f"Detected <blue>{pid!r}</blue> appended, loading...")
                            load_plugin(plugin_name)
                if new := (set(EntariConfig.instance.plugin) - set(old_plugin)):
                    for plugin_name in new:
                        if not (plugin := load_plugin(plugin_name)):
                            continue
                        plugin._load()
                        await plugin._startup()
                        await plugin._ready()
                        del plugin

    async def launch(self, manager: Launart):
        async with self.stage("blocking"):
            watch_task = asyncio.create_task(self.watch())
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            watch_config_task = asyncio.create_task(self.watch_config())
            done, pending = await any_completed(
                sigexit_task,
                watch_task,
                watch_config_task,
            )
            if sigexit_task in done:
                watch_task.cancel()
                watch_config_task.cancel()
        self.fail.clear()


plug = Plugin.current()
watch_dirs = plug.config.get("watch_dirs", ["."])
watch_config = plug.config.get("watch_config", False)

plug.service(serv := Watcher(watch_dirs, watch_config))


@plug.use(ConfigReload)
def handle_config_reload(event: ConfigReload):
    if event.scope != "plugin":
        return
    if event.key not in ("::auto_reload", "arclet.entari.builtins.auto_reload"):
        return
    serv.dirs = event.value.get("watch_dirs", ["."])
    serv.is_watch_config = event.value.get("watch_config", False)
    return True
