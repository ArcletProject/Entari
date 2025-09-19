import asyncio
from dataclasses import asdict
from pathlib import Path

from arclet.letoderea import post, publish
from launart import Launart, Service, any_completed
from launart.status import Phase
from loguru import logger as loguru_logger

try:
    from watchfiles import PythonFilter, awatch
except ModuleNotFoundError:
    raise ImportError("Please install `watchfiles` first. Install with `pip install arclet-entari[reload]`")

from arclet.entari import add_service, load_plugin, metadata, plugin_config
from arclet.entari.config import BasicConfModel, EntariConfig, model_field
from arclet.entari.event.config import ConfigReload
from arclet.entari.logger import log
from arclet.entari.plugin import find_plugin, find_plugin_by_file, unload_plugin_async

# declare_static()
loguru_logger.disable("watchfiles.main")


class Config(BasicConfModel):
    watch_dirs: list[str | Path] = model_field(
        default_factory=lambda: ["."],
        description="需要监视的目录列表，支持相对路径和绝对路径",
    )
    watch_config: bool = model_field(default=False, description="是否监视配置文件的变化，默认为 False")
    debounce: int = model_field(
        default=1600, description="防抖时间，单位为毫秒，防止频繁变动导致的重复加载，默认为 1600 毫秒"
    )
    step: int = model_field(default=50, description="轮询间隔，单位为毫秒，默认为 50 毫秒")


metadata(
    "Auto Reload",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="Auto reload plugins when files changed",
    config=Config,
    readme="""
# Auto Reload (Hot Module Replacement)

该插件提供自动监视指定目录下的 Python 文件变化并重新加载对应插件的功能。

## 配置

- `watch_dirs`: 需要监视的目录列表，支持相对路径和绝对路径，默认为当前目录 `["."]`
- `watch_config`: 是否监视配置文件的变化，默认为 `False`
- `debounce`: 防抖时间，单位为毫秒，防止频繁变动导致的重复加载，默认为 `1600` 毫秒
- `step`: 轮询间隔，单位为毫秒，默认为 `50` 毫秒

## 说明

1. 若插件被标记为静态 (通过 `declare_static()`, 或作为 prelude 插件)，其变动将被忽略。
2. 配置文件变动时：
    - auto_reload 会发布 `ConfigReload` 事件，其他插件可监听该事件以处理配置变动。
    - 若目标插件确认配置变动已被自身处理 (通过返回 `True`)，则不会重新加载该插件。
    - 若目标插件未处理配置变动，且非静态插件，则会尝试重新加载该插件。
    - 若插件配置在变动中被移除，则会卸载该插件。
""",
)


logger = log.wrapper("[AutoReload]").opt(colors=True)


class Watcher(Service):
    id = "entari.plugin.auto_reload/watcher"

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    def __init__(self, config: Config):
        self.config = config
        self.fail: dict[str, tuple[str, dict]] = {}
        super().__init__()

    async def watch(self):
        async for event in awatch(
            *self.config.watch_dirs, debounce=self.config.debounce, step=self.config.step, watch_filter=PythonFilter()
        ):
            for change in event:
                if plugin := find_plugin_by_file(change[1]):
                    if plugin.is_static:
                        logger.info(f"Plugin <y>{plugin.id!r}</y> is static, ignored.")
                        continue
                    logger.info(f"Detected change in <blue>{plugin.id!r}</blue>, reloading...")
                    pid = plugin.id
                    _conf = plugin.config.copy()
                    del plugin
                    await unload_plugin_async(pid)
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
        async for event in awatch(
            file.absolute(),
            *(dir_.absolute() for dir_ in extra),
            debounce=self.config.debounce,
            step=self.config.step,
            recursive=False,
        ):
            for change in event:
                if not self.config.watch_config:
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
                        await publish(ConfigReload("basic", key, new_basic[key], old_basic[key]))
                for key in set(new_basic) - set(old_basic):
                    logger.debug(f"Basic config <y>{key!r}</y> appended")
                    await publish(ConfigReload("basic", key, new_basic[key]))
                for plugin_name in old_plugin:
                    if plugin_name.startswith("$"):
                        continue
                    pid = plugin_name.replace("::", "arclet.entari.builtins.")
                    if plugin_name not in EntariConfig.instance.plugin:
                        if plugin := find_plugin(pid):
                            if plugin.is_static:
                                logger.info(f"Plugin <y>{plugin.id!r}</y> is static, ignored.")
                            else:
                                del plugin
                                await unload_plugin_async(pid)
                                logger.info(f"Disposed plugin <blue>{pid!r}</blue>")
                        continue
                    old_conf = EntariConfig._clean(old_plugin[plugin_name])
                    new_conf = EntariConfig.instance.plugin[plugin_name]
                    if old_conf != new_conf:
                        logger.debug(
                            f"Plugin <y>{plugin_name!r}</y> config changed from <r>{old_conf!r}</r> "
                            f"to <g>{new_conf!r}</g>",
                        )

                        if plugin := find_plugin(pid):
                            added = set(new_conf) - set(old_conf)
                            removed = set(old_conf) - set(new_conf)
                            changed = {k for k in set(new_conf) & set(old_conf) if new_conf[k] != old_conf[k]}
                            changes = added | removed | changed
                            if "$disable" in changes:
                                plugin.disable() if new_conf.get("$disable", False) else plugin.enable()
                                changes.remove("$disable")
                            if "$dry" in changes:
                                changes.remove("$dry")
                                if new_conf.get("$dry", False):
                                    logger.debug(f"Plugin <y>{plugin.id!r}</y> is dry, ignored.")
                                    continue
                            if not changes:
                                continue
                            res = await post(
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

                            async def _():
                                await unload_plugin_async(pid)
                                if plugin := load_plugin(plugin_name, new_conf):
                                    logger.info(f"Reloaded <blue>{plugin.id!r}</blue>")
                                    del plugin
                                else:
                                    logger.error(f"Failed to reload <blue>{plugin_name!r}</blue>")
                                    self.fail[plugin_file] = (pid, _conf)

                            await asyncio.shield(_())
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
        async with self.stage("preparing"):
            logger.info(f"Watching directories: {', '.join(repr(d) for d in self.config.watch_dirs)}")
            if self.config.watch_config:
                logger.info("Watching config file changes")
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
add_service(Watcher(conf))
