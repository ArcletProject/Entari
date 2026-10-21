from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any, Final

from arclet.letoderea import post, publish

from ..config.action import config_model_dump
from ..config.file import EntariConfig
from ..config.model import ApplyError, ApplyReport, FailEntry
from ..event.config import ConfigModify, ConfigReload
from ..logger import log
from .loader import find_plugin, load_plugin, reload_plugin, reload_subplugin, unload_plugin_async
from .model import Plugin
from .service import plugin_service


def _diff_basic(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    keys = []
    for key in old:
        if key not in new or old[key] != new[key]:
            keys.append(key)
    for key in new:
        if key not in old:
            keys.append(key)
    return keys


def _is_plugin_key(key: str) -> bool:
    return not key.startswith(("$", "~", "?"))


def _plugin_id(name: str) -> str:
    return name.replace("::", "arclet.entari.builtins.")


def _tree_id(plugin_id: str) -> str:
    while plugin_id in plugin_service._subplugined:
        plugin_id = plugin_service._subplugined[plugin_id]
    return plugin_id


def _visible(conf: dict[str, Any]) -> dict[str, Any]:
    # $path/$static 是运行时注入的，不属于用户配置
    return {k: deepcopy(v) for k, v in conf.items() if k not in ("$path", "$static")}


def _plugin_file(plg: Plugin) -> str:
    return str(plg.module.__file__) if plg.module.__file__ else plg.id


class ConfigApplier:
    def __init__(self) -> None:
        self._apply_lock = asyncio.Lock()
        self._plugin_locks: dict[str, asyncio.Lock] = {}
        self.fail: dict[str, FailEntry] = {}

    def lock_for(self, plugin_id: str) -> asyncio.Lock:
        key = _tree_id(plugin_id)
        lock = self._plugin_locks.get(key)
        if lock is None:
            lock = self._plugin_locks[key] = asyncio.Lock()
        return lock

    def _is_relevant_path(self, target: Path, cfg: EntariConfig) -> bool:
        root = Path(cfg.path).resolve()
        if target == root:
            return True
        for raw in cfg.plugin_extra_files:
            extra = Path(raw)
            if not extra.is_absolute():
                extra = root.parent / extra
            extra = extra.resolve()
            if target == extra or target.is_relative_to(extra):
                return True
        return False

    async def reload(self, plugin_id: str, config: dict[str, Any] | None = None):
        async with self.lock_for(plugin_id):
            if plugin_id in plugin_service._subplugined:
                return await reload_subplugin(plugin_id, config)
            return await reload_plugin(plugin_id, config)

    async def apply(self, path: str | Path | None = None, *, source="unknown", force=True) -> ApplyReport:
        if not hasattr(EntariConfig, "instance"):
            return ApplyReport(ok=False, errors=[ApplyError(None, "config is not loaded")])
        cfg = EntariConfig.instance

        target = Path(path).resolve() if path is not None else Path(cfg.path).resolve()
        if path is not None and not self._is_relevant_path(target, cfg):
            log.config.debug(f"Ignored config change for irrelevant path: {target}")
            return ApplyReport(ok=True, applied=False, ignored=f"irrelevant path: {target}")

        async with self._apply_lock:
            old_basic = config_model_dump(cfg.basic)
            old_plugin = deepcopy(cfg.plugin)

            log.config.info(f"Detected config change in {str(target)!r} (source={source!r}), applying...")

            try:
                if path is None or target == Path(cfg.path).resolve():
                    reloaded = cfg.reload(force=force)
                else:
                    reloaded = cfg.reload_file(target, force=force)
                if not reloaded:
                    return ApplyReport(ok=True, applied=False)
            except Exception as exc:
                log.config.error(f"Failed to reload config from {str(target)!r}: {exc!r}")
                return ApplyReport(
                    ok=False,
                    errors=[ApplyError(None, f"reload failed: {exc}", exc)],
                )

            report = ApplyReport()

            new_basic = config_model_dump(cfg.basic)
            report.changed_basic = _diff_basic(old_basic, new_basic)
            await self._apply_basic(old_basic, new_basic, report)

            await self._apply_plugins(old_plugin, cfg.plugin, report)

            report.applied = bool(
                report.changed_basic or report.changed_plugins or report.loaded or report.unloaded or report.reloaded
            )
            report.ok = not report.errors
            if report.applied:
                log.config.debug(
                    f"Config apply from {source!r} finished: "
                    f"basic={report.changed_basic}, loaded={report.loaded}, "
                    f"unloaded={report.unloaded}, reloaded={report.reloaded}, "
                    f"skipped={report.skipped}"
                )
            else:
                log.config.debug(f"Config apply from {source!r}: no semantic changes.")

            if report.errors:
                log.config.warning(
                    f"Config apply from {source!r} finished with " f"{len(report.errors)} error(s): {report.errors}"
                )
            return report

    async def retry(self, file_path: str) -> bool:
        entry = self.fail.get(file_path)
        if entry is None:
            return False

        # 插件已经被移除/替换，失败记录作废
        if find_plugin(entry.plugin_id) is None:
            log.config.debug(f"Failed plugin <y>{entry.plugin_id!r}</y> no longer exists, drop fail record.")
            self.fail.pop(file_path, None)
            return False

        log.config.info(f"Detected change in {file_path!r} which failed to reload, retrying...")
        try:
            result = await self.reload(entry.plugin_id, deepcopy(entry.config))
        except Exception as e:
            log.config.error(f"Failed to reload <blue>{entry.plugin_id!r}</blue>: {e!r}")
            return False

        if result:
            log.config.info(f"Reloaded <blue>{entry.plugin_id!r}</blue>")
            self.fail.pop(file_path, None)
            return True
        log.config.error(f"Failed to reload <blue>{entry.plugin_id!r}</blue>: {result.error!r}")
        return False

    async def _apply_basic(self, old, new, report):
        for key in report.changed_basic:
            if key in new:
                old_value = old.get(key)
                if key in old:
                    log.config.debug(
                        f"Basic config <y>{key!r}</y> changed from <r>{old_value!r}</r> to <g>{new[key]!r}</g>"
                    )
                else:
                    log.config.debug(f"Basic config <y>{key!r}</y> appended: <g>{new[key]!r}</g>")
                await publish(ConfigReload("basic", key, new[key], old.get(key)))
            else:
                log.config.debug(f"Basic config <y>{key!r}</y> removed (was <r>{old[key]!r}</r>)")
                await publish(ConfigReload("basic", key, None, old[key]))

    async def _apply_plugins(self, old_plugins, new_plugins, report):
        old_names = {k for k in old_plugins if _is_plugin_key(k)}
        new_names = {k for k in new_plugins if _is_plugin_key(k)}

        for name in sorted(old_names - new_names):
            await self._remove_plugin(name, old_plugins[name], report)

        for name in sorted(new_names - old_names):
            await self._add_plugin(name, new_plugins[name], report)

        for name in sorted(old_names & new_names):
            await self._change_plugin(name, old_plugins[name], new_plugins[name], report)

    async def _remove_plugin(self, name, conf, report):
        pid = _plugin_id(name)
        if await self._unload(pid):
            report.unloaded.append(pid)
        else:
            report.skipped.append(pid)
        self._clear_fail(pid)

    async def _unload(self, pid: str) -> bool:
        async with self.lock_for(pid):
            plg = find_plugin(pid)
            if plg is None:
                log.config.debug(f"Plugin <y>{pid!r}</y> is not loaded, nothing to unload.")
                return False
            if plg.is_static:
                log.config.info(f"Plugin <y>{pid!r}</y> is static, ignored.")
                return False
            if pid in plugin_service._subplugined:
                tasks = plg.dispose()
                if tasks:
                    await asyncio.wait(tasks)
            else:
                await unload_plugin_async(pid)
            return True

    async def _add_plugin(self, name, conf, report):
        if conf.get("$optional", False):
            log.config.debug(f"Plugin <y>{name!r}</y> is optional and not loaded, ignored.")
            report.skipped.append(name)
            return

        pid = _plugin_id(name)
        if plg := find_plugin(pid):
            # 手动加载过的 optional 插件，或配置里已有但 live 未记录：按修改处理
            await self._change_plugin(name, _visible(plg.config), conf, report)
            return

        log.config.info(f"Detected <blue>{pid!r}</blue> appended, loading...")
        async with self.lock_for(pid):
            result = load_plugin(name, deepcopy(conf))

        if result:
            log.config.info(f"Loaded <blue>{pid!r}</blue>")
            report.loaded.append(pid)
            self._clear_fail(pid)
        else:
            log.config.error(f"Failed to load <blue>{name!r}</blue>: {result.error!r}")
            self._record_fail(pid, conf, result.error)
            report.errors.append(ApplyError(pid, str(result.error), result.error))

    async def _change_plugin(self, name, old_raw, new_raw, report):
        pid = _plugin_id(name)
        plg = find_plugin(pid)
        old_conf = _visible(old_raw)
        new_conf = _visible(new_raw)

        if old_conf == new_conf:
            log.config.trace(f"Plugin <y>{pid!r}</y> config has no semantic difference, skipped.")
            return

        report.changed_plugins.append(pid)
        log.config.debug(f"Plugin <y>{name!r}</y> config changed from <r>{old_conf!r}</r> to <g>{new_conf!r}</g>")

        # 1. $optional：变为 optional 时卸载；一直是 optional 且未加载则跳过
        if new_raw.get("$optional", False):
            if not old_raw.get("$optional", False):
                if await self._unload(pid):
                    report.unloaded.append(pid)
                else:
                    report.skipped.append(pid)
                return
            if plg is None:
                log.config.debug(f"Plugin <y>{pid!r}</y> is optional and not loaded, ignored.")
                report.skipped.append(pid)
                return
            # 一直是 optional 但被手动加载：继续按普通配置变更处理

        # 2. 插件当前没加载：通常是 optional -> enabled，或启动时缺失
        if plg is None:
            await self._add_plugin(name, new_raw, report)
            return

        added = set(new_conf) - set(old_conf)
        removed = set(old_conf) - set(new_conf)
        changed = {k for k in set(old_conf) & set(new_conf) if old_conf[k] != new_conf[k]}
        changes = added | removed | changed

        if not changes:
            log.config.debug(f"Plugin <y>{pid!r}</y> config has no semantic difference, skipped.")
            return

        log.config.trace(
            f"Plugin <y>{name!r}</y> changes: "
            f"added={sorted(added)}, removed={sorted(removed)}, changed={sorted(changed)}"
        )

        # 3. $disable：只切换运行状态，不重载
        if "$disable" in changes:
            old_plugin_config = plg.config
            plg.config = new_raw
            try:
                tasks = plg.check_disable()
                if tasks:
                    await asyncio.wait(tasks)
                log.config.debug(f"Plugin <y>{pid!r}</y> $disable changed, runtime state updated.")
            except Exception as exc:
                plg.config = old_plugin_config
                log.config.error(f"Failed to update <blue>{pid!r}</blue> disable state: {exc!r}")
                report.errors.append(ApplyError(pid, f"check_disable failed: {exc}", exc))
                return
            changes.discard("$disable")

        if not changes:
            return

        # 4. static 不重载，但仍发 ConfigReload（沿用现有行为）
        try:
            handled = await post(ConfigReload("plugin", name, deepcopy(new_raw), old_conf))
        except Exception as exc:
            report.errors.append(ApplyError(pid, f"ConfigReload handler failed: {exc}", exc))
            return

        if handled is not None and handled.value:
            log.config.debug(f"Plugin <y>{pid!r}</y> config change handled by itself.")
            report.skipped.append(pid)
            return

        if plg.is_static:
            log.config.info(f"Plugin <y>{pid!r}</y> is static, ignored.")
            report.skipped.append(pid)
            return

        log.config.info(f"Detected config of <blue>{pid!r}</blue> changed, reloading...")
        try:
            result = await self.reload(pid, deepcopy(new_raw))
        except Exception as exc:
            log.config.error(f"Failed to reload <blue>{name!r}</blue>: {exc!r}")
            report.errors.append(ApplyError(pid, f"reload failed: {exc}", exc))
            self._record_fail(pid, new_raw, exc)
            return

        if result:
            log.config.info(f"Reloaded <blue>{pid!r}</blue>")
            report.reloaded.append(pid)
            self._clear_fail(pid)
        else:
            log.config.error(f"Failed to reload <blue>{name!r}</blue>: {result.error!r}")
            report.errors.append(ApplyError(pid, str(result.error), result.error))
            self._record_fail(pid, new_raw, result.error)

    def _record_fail(self, pid: str, conf: dict, exc: BaseException) -> None:
        plg = find_plugin(pid)
        key = _plugin_file(plg) if plg is not None else pid
        self.fail[key] = FailEntry(
            plugin_id=pid,
            config=deepcopy(conf),
            file=key,
            message=str(exc),
        )

    def _clear_fail(self, pid: str) -> None:
        for key, entry in list(self.fail.items()):
            if entry.plugin_id == pid:
                self.fail.pop(key, None)


applier: Final[ConfigApplier] = ConfigApplier()


async def handle_config_modify(event: ConfigModify) -> ApplyReport:
    return await applier.apply(event.path, source=event.source)
