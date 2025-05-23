import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Union

from arclet.letoderea import es
from launart import Launart, Service, any_completed
from launart.status import Phase
from loguru import logger as loguru_logger

try:
    from watchfiles import PythonFilter, awatch
except ModuleNotFoundError:
    raise ImportError("Please install `watchfiles` first. Install with `pip install arclet-entari[reload]`")

from arclet.entari import add_service, declare_static, load_plugin, metadata, plugin_config, unload_plugin
from arclet.entari.config import BasicConfModel, EntariConfig, config_model_validate, field
from arclet.entari.event.config import ConfigReload
from arclet.entari.logger import log
from arclet.entari.plugin import find_plugin, find_plugin_by_file

declare_static()
loguru_logger.disable("watchfiles.main")


class Config(BasicConfModel):
    watch_dirs: list[Union[str, Path]] = field(default_factory=lambda: ["."])
    watch_config: bool = False


metadata(
    "AutoReload",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="Auto reload plugins when files changed",
    config=Config,
)


logger = log.wrapper("[AutoReload]").opt(colors=True)


def detect_filter_change(old: dict, new: dict):
    added = set(new) - set(old)
    removed = set(old) - set(new)
    changed = {key for key in set(new) & set(old) if new[key] != old[key]}
    return "allow" in (added | removed | changed) or "$deny" in (added | removed | changed)


class Watcher(Service):
    id = "entari.plugin.auto_reload/watcher"

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"blocking", "cleanup"}

    def __init__(self, dirs: list[Union[str, Path]], is_watch_config: bool):
        self.dirs = dirs
        self.is_watch_config = is_watch_config
        self.fail: dict[str, tuple[str, dict]] = {}
        super().__init__()

    async def watch(self):
        async for event in awatch(*self.dirs, watch_filter=PythonFilter()):
            for change in event:
                if plugin := find_plugin_by_file(change[1]):
                    if plugin.is_static:
                        logger.info(f"Plugin <y>{plugin.id!r}</y> is static, ignored.")
                        continue
                    logger.info(f"Detected change in <blue>{plugin.id!r}</blue>, reloading...")
                    pid = plugin.id
                    _conf = plugin.config.copy()
                    del plugin
                    unload_plugin(pid)
                    if plugin := load_plugin(pid, _conf):
                        logger.info(f"Reloaded <blue>{plugin.id!r}</blue>")
                        del plugin
                    else:
                        logger.error(f"Failed to reload <blue>{pid!r}</blue>")
                        self.fail[change[1]] = (pid, _conf)
                elif change[1] in self.fail:
                    logger.info(f"Detected change in {change[1]!r} which failed to reload, retrying...")
                    if plugin := load_plugin(*self.fail[change[1]]):
                        logger.info(f"Reloaded <blue>{plugin.id!r}</blue>")
                        del plugin
                        del self.fail[change[1]]
                    else:
                        logger.error(f"Failed to reload <blue>{self.fail[change[1]][0]!r}</blue>")

    async def watch_config(self):
        file = EntariConfig.instance.path.resolve()
        extra = [file.parent.joinpath(path) for path in EntariConfig.instance.plugin_extra_files]
        async for event in awatch(file.absolute(), *(dir_.absolute() for dir_ in extra), recursive=False):
            for change in event:
                if not self.is_watch_config:
                    continue
                if not (
                    (change[0].name == "modified" and Path(change[1]).resolve() == file)
                    or Path(change[1]).resolve() in extra
                    or Path(change[1]).resolve().parent in extra
                ):
                    continue
                old_basic = asdict(EntariConfig.instance.basic)  # noqa
                old_plugin = EntariConfig.instance.plugin.copy()
                if not EntariConfig.instance.reload():
                    continue
                logger.info(f"Detected change in {change[1]!r}, reloading config...")
                new_basic = asdict(EntariConfig.instance.basic)  # noqa
                for key in old_basic:
                    if key in new_basic and old_basic[key] != new_basic[key]:
                        logger.debug(
                            f"Basic config <y>{key!r}</y> changed from <r>{old_basic[key]!r}</r> "
                            f"to <g>{new_basic[key]!r}</g>",
                        )
                        await es.publish(ConfigReload("basic", key, new_basic[key], old_basic[key]))
                for key in set(new_basic) - set(old_basic):
                    logger.debug(f"Basic config <y>{key!r}</y> appended")
                    await es.publish(ConfigReload("basic", key, new_basic[key]))
                for plugin_name in old_plugin:
                    if plugin_name.startswith("$") or plugin_name.startswith("~"):
                        continue
                    pid = plugin_name.replace("::", "arclet.entari.builtins.")
                    if plugin_name not in EntariConfig.instance.plugin:
                        if plugin := find_plugin(pid):
                            if plugin.is_static:
                                logger.info(f"Plugin <y>{plugin.id!r}</y> is static, ignored.")
                            else:
                                del plugin
                                unload_plugin(pid)
                                logger.info(f"Disposed plugin <blue>{pid!r}</blue>")
                        continue
                    if old_plugin[plugin_name] != EntariConfig.instance.plugin[plugin_name]:
                        logger.debug(
                            f"Plugin <y>{plugin_name!r}</y> config changed from <r>{old_plugin[plugin_name]!r}</r> "
                            f"to <g>{EntariConfig.instance.plugin[plugin_name]!r}</g>",
                        )
                        old_conf = old_plugin[plugin_name]
                        new_conf = EntariConfig.instance.plugin[plugin_name]
                        if plugin := find_plugin(pid):
                            filter_changed = detect_filter_change(old_conf, new_conf)
                            if not filter_changed:
                                res = await es.post(
                                    ConfigReload("plugin", plugin_name, new_conf, old_conf),
                                )
                                if res and res.value:
                                    logger.debug(f"Plugin <y>{pid!r}</y> config change handled by itself.")
                                    continue
                            if plugin.is_static:
                                logger.info(f"Plugin <y>{plugin.id!r}</y> is static, ignored.")
                                continue
                            logger.info(f"Detected config of <blue>{pid!r}</blue> changed, reloading...")
                            plugin_file = str(plugin.module.__file__)
                            _conf = plugin.config.copy()
                            unload_plugin(pid)
                            if plugin := load_plugin(plugin_name, new_conf):
                                logger.info(f"Reloaded <blue>{plugin.id!r}</blue>")
                                del plugin
                            else:
                                logger.error(f"Failed to reload <blue>{plugin_name!r}</blue>")
                                self.fail[plugin_file] = (pid, _conf)
                        else:
                            logger.info(f"Detected <blue>{pid!r}</blue> appended, loading...")
                            load_plugin(plugin_name, new_conf)
                if new := (set(EntariConfig.instance.plugin) - set(old_plugin)):
                    for plugin_name in new:
                        if plugin_name.startswith("$") or plugin_name.startswith("~"):
                            continue
                        if not (plugin := load_plugin(plugin_name)):
                            continue
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
        async with self.stage("cleanup"):
            self.fail.clear()


conf = plugin_config(Config)

add_service(serv := Watcher(conf.watch_dirs, conf.watch_config))


@es.on(ConfigReload)
def handle_config_reload(event: ConfigReload):
    if event.scope != "plugin":
        return None
    if event.key not in ("::auto_reload", "arclet.entari.builtins.auto_reload"):
        return None
    new_conf = config_model_validate(Config, event.value)
    serv.dirs = new_conf.watch_dirs
    serv.is_watch_config = new_conf.watch_config
    return True
