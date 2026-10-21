import ast
import asyncio
import importlib
import sys
from pathlib import Path
from traceback import format_exception_only
from types import ModuleType

from launart import Launart, Service, any_completed
from launart.status import Phase
from loguru import logger as loguru_logger

from arclet.entari.config.model import FailEntry

try:
    from watchfiles import PythonFilter, awatch
except ModuleNotFoundError:
    raise ImportError("Please install `watchfiles` first. Install with `pip install arclet-entari[reload]`")

from arclet.entari import add_service, metadata, plugin_config
from arclet.entari.config import BasicConfModel, EntariConfig, model_field
from arclet.entari.logger import log
from arclet.entari.plugin import (
    Plugin,
    PluginRole,
    find_plugin_by_file,
    plugin_service,
)
from arclet.entari.plugin.apply import applier
from arclet.entari.plugin.swap import classify, swap_functions
from arclet.entari.utils import escape_tag

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
    PluginRole.UTILITY,
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="自动监视指定目录下的 Python 或配置文件变化并重新加载对应插件",
    config=Config,
    readme="""
# Auto Reload (Hot Module Replacement)

该插件提供自动监视指定目录下的 Python 或配置文件变化并重新加载对应插件的功能。

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


def module_name_from_path(path: Path) -> str | None:
    path = Path(path).resolve()

    for entry in map(Path, sys.path):
        try:
            relative = path.relative_to(entry.resolve())
        except ValueError:
            continue

        if relative.suffix == ".py":
            relative = relative.with_suffix("")

        parts = list(relative.parts)

        # __init__.py 对应包本身
        if parts[-1] == "__init__":
            parts.pop()

        return ".".join(parts)

    return None


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
        self.fail = applier.fail
        super().__init__()

    async def _reload_upstream(self, module_name: str) -> list[str]:
        """刷新非插件上游模块，并重载依赖它的插件

        必须先刷新 sys.modules 中的内容, 否则依赖插件重载时 import 链命中 sys.modules 缓存，拿到的仍是旧模块。

        Returns:
            实际重载的插件 id 列表（供同批次去重）。
        """
        if module_name in plugin_service.plugins or module_name in plugin_service._subplugined:
            return []
        mod = sys.modules.get(module_name)
        if mod is None or not isinstance(mod, ModuleType):
            return []
        dependents = plugin_service.dependents_of(module_name, ensure=True)
        if not dependents:
            return []
        plugins = ", ".join(sorted(dependents))
        logger.debug(f"Reloading upstream module <y>{module_name!r}</y>, affected plugins: <red>{plugins}</red>")
        try:
            importlib.reload(mod)
        except Exception as e:
            logger.error(f"Failed to reload upstream module <blue>{module_name!r}</blue>: {e!r}")
            return []
        reloaded: list[str] = []
        for dep_id in plugin_service.topo_dependents(set(dependents)):
            result = await applier.reload(dep_id)
            if result:
                reloaded.append(dep_id)
            else:
                logger.error(f"Failed to reload plugin <blue>{dep_id!r}</blue> after upstream module reload")
        return reloaded

    async def watch(self):
        async for event in awatch(
            *self.config.watch_dirs, debounce=self.config.debounce, step=self.config.step, watch_filter=PythonFilter()
        ):
            pending: dict[str, tuple[str, Plugin]] = {}
            failed: list[str] = []
            upstream: set[str] = set()
            for change in event:
                if plugin := find_plugin_by_file(change[1]):
                    if plugin.is_static:
                        logger.info(f"Plugin <y>{plugin.id!r}</y> is static, ignored.")
                        continue
                    pending.setdefault(plugin.id, (change[1], plugin))
                elif change[1] in self.fail:
                    failed.append(change[1])
                elif module_name := module_name_from_path(Path(change[1])):
                    upstream.add(module_name)
            reloaded: set[str] = set()
            for module_name in upstream:
                reloaded.update(await self._reload_upstream(module_name))
            for pid, (file_path, plugin) in pending.items():
                if pid in reloaded:
                    self.fail.pop(file_path, None)
                    continue
                nodes: ast.Module | None = None
                if (
                    plugin._inspect
                    and plugin.module.__file__
                    and (path := Path(file_path).resolve()) == Path(plugin.module.__file__).resolve()
                ):
                    try:
                        nodes = ast.parse(path.read_bytes(), filename=path, type_comments=True)
                    except (OSError, SyntaxError) as e:
                        trace = escape_tag("".join(format_exception_only(e)))
                        logger.error(f"Change in <blue>{pid!r}</blue> occurred exception, skipped:\n{trace}")
                        continue
                    else:
                        if ast.dump(nodes, include_attributes=False) == plugin._inspect.dump:
                            logger.debug(f"Change in <y>{pid!r}</y> has no semantic difference, skipped.")
                            self.fail.pop(file_path, None)
                            continue
                logger.info(f"Detected change in <blue>{pid!r}</blue>, reloading...")
                if plugin._inspect and nodes:
                    changes = classify(plugin._inspect.nodes, nodes)
                    if changes is not None and swap_functions(plugin, nodes, changes):
                        if changes:
                            logger.info(
                                f"Hot swapped functions in <blue>{pid!r}</blue>: "
                                f"{', '.join(f'<m>{change.qualname}</m>' for change in changes)} "
                                f"successfully."
                            )
                        else:
                            logger.debug(f"Change in <y>{pid!r}</y> has no function-level diff, skipped.")
                        self.fail.pop(file_path, None)
                        continue
                    logger.debug(f"Hot swap functions in <y>{pid!r}</y> failed, falling back to full reload.")
                _conf = plugin.config.copy()
                del plugin
                if res := await applier.reload(pid, _conf):
                    logger.info(f"Reloaded <blue>{pid!r}</blue>")
                    self.fail.pop(file_path, None)
                else:
                    logger.error(f"Failed to reload <blue>{pid!r}</blue>: {res.error!r}")
                    self.fail[file_path] = FailEntry(pid, _conf, file_path)
            pending.clear()
            for file_path in failed:
                await applier.retry(file_path)

    async def watch_config(self):
        cfg = EntariConfig.instance
        file = cfg.path.resolve()
        extra = [file.parent.joinpath(path) for path in cfg.plugin_extra_files]

        async for event in awatch(
            file.absolute(),
            *(dir_.absolute() for dir_ in extra),
            debounce=self.config.debounce,
            step=self.config.step,
            recursive=False,
        ):
            if not self.config.watch_config:
                continue
            relevant = [
                change
                for change in event
                if not change[1].endswith(".schema.json")
                and (
                    (change[0].name == "modified" and Path(change[1]).resolve() == file)
                    or Path(change[1]).resolve() in extra
                    or Path(change[1]).resolve().parent in extra
                )
            ]
            if not relevant:
                continue
            changed = Path(relevant[0][1]).resolve()
            logger.debug(f"Config file change detected: {str(changed)!r}")
            report = await applier.apply(file, source="auto_reload")
            if not report.ok:
                logger.error(f"Config apply finished with errors: {report.errors}")

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
