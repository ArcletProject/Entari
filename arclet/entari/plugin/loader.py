import ast
import asyncio
import sys
from typing import Any, overload
from weakref import ref

from arclet.letoderea import publish
from arclet.letoderea.scope import _scopes

from ..config import EntariConfig
from ..event.lifespan import Ready
from ..event.plugin import PluginLoadedFailed
from ..exceptions import RegisterNotInPluginError, ReusablePluginError, StaticPluginDispatchError
from ..logger import log
from .model import Plugin, current_plugin
from .module import import_plugin
from .service import plugin_service


def collect_module_level_names(nodes: ast.Module) -> set[str]:
    """收集模块层表达式引用的名字（函数体除外；含装饰器/默认值/注解/基类/类级语句）"""
    used: set[str] = set()

    def visit_expr(expr: ast.expr):
        if isinstance(expr, ast.Name) and isinstance(expr.ctx, ast.Load):
            used.add(expr.id)
            return
        for child in ast.iter_child_nodes(expr):
            if isinstance(child, ast.expr):
                visit_expr(child)
            elif isinstance(child, ast.keyword) and child.value is not None:
                visit_expr(child.value)

    def visit_stmt(stmt: ast.stmt):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in stmt.decorator_list:
                visit_expr(dec)
            for default in [*stmt.args.defaults, *[d for d in stmt.args.kw_defaults if d]]:
                visit_expr(default)
            for arg in stmt.args.posonlyargs + stmt.args.args + stmt.args.kwonlyargs:
                if arg.annotation:
                    visit_expr(arg.annotation)
            if stmt.args.vararg and stmt.args.vararg.annotation:
                visit_expr(stmt.args.vararg.annotation)
            if stmt.args.kwarg and stmt.args.kwarg.annotation:
                visit_expr(stmt.args.kwarg.annotation)
            return
        if isinstance(stmt, ast.ClassDef):
            for dec in stmt.decorator_list:
                visit_expr(dec)
            for base in stmt.bases:
                visit_expr(base)
            for kw in stmt.keywords:
                visit_expr(kw.value)
            for s in stmt.body:
                visit_stmt(s)
            return
        for child in ast.iter_child_nodes(stmt):
            if isinstance(child, ast.expr):
                visit_expr(child)
            elif isinstance(child, ast.stmt):
                visit_stmt(child)
            elif isinstance(child, ast.keyword) and child.value is not None:
                visit_expr(child.value)

    for stmt in nodes.body:
        visit_stmt(stmt)
    return used


def _uses_module_level(plugin: Plugin, path: str) -> bool:
    """检测插件是否在模块层使用 path 的绑定名（基类/模块级装饰器/顶层实例化等）"""
    if not plugin._inspect:
        return True
    bound = {
        name
        for name, (target, _) in plugin_service.last_bindings(plugin.id).items()
        if target == path or target.startswith(path + ".")
    }
    if not bound:
        return False
    return bool(collect_module_level_names(plugin._inspect.nodes) & bound)


_MISSING = object()


def _rebind_imports(plugin: Plugin, path: str) -> bool:
    """将插件对 path（或其子树）的 import 绑定改写为新对象；False 表示有绑定无法满足（升级全量）

    模块绑定（attr 为 None）仅在名字等同于目标模块或其末组件时写回：`import a.b` 风格的名字是顶层包，
    其子模块链由 promote 的父属性写回维护，不在此处理。
    绑定目标为 path 的父包、且父包绑定记录将该名字解析到 path 时，
    经父模块 getattr 取新值（父包在 sorted 依赖序中先于其子模块处理，故已重绑完成）。
    """
    module = plugin.module
    parent_pkg = path.rpartition(".")[0]
    for name, (target, attr) in plugin_service.last_bindings(plugin.id).items():
        if target == path or target.startswith(path + "."):
            if target not in plugin_service.plugins:
                continue
            new_module = plugin_service.plugins[target].module
            if attr is None:
                if name != target and name != target.rpartition(".")[-1]:
                    continue
                value: Any = new_module
            else:
                value = getattr(new_module, attr, _MISSING)
                if value is _MISSING:
                    return False
            module.__dict__[name] = value
        elif (
            parent_pkg
            and attr is not None
            and target == parent_pkg
            and parent_pkg in plugin_service.bindings
            and parent_pkg in plugin_service.plugins
        ):
            parent_chain = plugin_service.last_bindings(parent_pkg)
            if parent_chain.get(attr or name, (None, None))[0] == path:
                value = getattr(plugin_service.plugins[parent_pkg].module, attr or name, _MISSING)
                if value is _MISSING:
                    return False
                module.__dict__[name] = value
    return True


def public_fingerprint(plugin: Plugin) -> str | None:
    """插件公开面指纹：排序后的导出名 + 各名字的定义节点的dump（导入名仅记录类型）

    无 `__all__` 时导出名 = 非下划线开头的模块 dict 名字；定义节点 dump 覆盖函数体与类体，任何行为差异都反映为指纹差异。
    """
    if not plugin._inspect:
        return None
    module = plugin.module
    names = getattr(module, "__all__", None)
    if names is None:
        names = sorted(n for n in module.__dict__ if not n.startswith("_"))
    else:
        names = sorted(names)
    node_map: dict[str, ast.stmt] = {}
    for stmt in plugin._inspect.nodes.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            node_map[stmt.name] = stmt
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    node_map[target.id] = stmt
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            node_map[stmt.target.id] = stmt
    parts: list[str] = []
    for name in names:
        if node := node_map.get(name):
            parts.append(f"{name}:{ast.dump(node, include_attributes=False)}")
        else:
            value = module.__dict__.get(name, None)
            parts.append(f"{name}:imported:{type(value).__name__}")
    return "\n".join(parts)


def _fingerprint_changed(plugin: Plugin) -> bool:
    """比较插件公开面指纹（存储的旧指纹 vs 现算新指纹），并更新存储

    旧指纹缺失（未存储过）时视为已变化：无法证明公开面未变 → 保守级联。
    """
    path = plugin.path
    old = plugin_service.fingerprints.get(path)
    new = public_fingerprint(plugin)
    plugin_service.fingerprints[path] = new or ""
    return old is None or old != new


def _rebind_dep(dep: Plugin, path: str):
    """重绑依赖方对 path 的 import 绑定并恢复其可用状态"""
    if _rebind_imports(dep, path):
        log.plugin.debug(f"rebound <y>{dep.id!r}</y>'s imports on <y>{path}</y>")
        dep.enable()
    else:
        log.plugin.warning(f"cannot satisfy <y>{dep.id!r}</y>'s imports on <y>{path}</y>, falling back to full reload")
        _cascade_dep(dep.id, plugin_service.referents.get(path, set()), set())


def _cascade_dep(dep_id: str, referent_set: set[str], recursive_guard: set[str]):
    """对依赖方执行全量级联（unload + load + Ready），失败时恢复 referent 边"""
    referent_set.discard(dep_id)
    log.plugin.debug(f"reloading <y>{dep_id!r}</y>")
    _unload_for_reload(dep_id)
    if not (result := load_plugin(dep_id)):
        referent_set.add(dep_id)
    else:
        publish(Ready(), result.plugin._scope)
        recursive_guard.add(dep_id)


def _handle_dependents(plugin: Plugin, recursive_guard: set[str] | None = None):
    """插件完成（重）加载后处理依赖方：公开面未变 → 全部重绑；否则按模块层使用细粒度重绑或级联

    依赖方 = referents 图与绑定索引的并集；公开面指纹未变时新对象与旧对象行为等价，模块层绑定无需重执行；
    指纹变化时仅模块层使用方升级全量，惰性依赖方重绑即可。
    """
    if recursive_guard is None:
        recursive_guard = set()
    path = plugin.path
    dependents = set(plugin_service.referents.get(path, ())) | set(plugin_service.dependents_of(path, ensure=False))
    if not dependents:
        return
    surface_changed = _fingerprint_changed(plugin)
    referent_set = plugin_service.referents.setdefault(path, set())
    current = current_plugin.get(None)
    for dep_id in plugin_service.topo_dependents(dependents):
        if dep_id in recursive_guard:
            continue
        if current is not None and (dep_id == current.id or dep_id.startswith(current.id + ".")):
            # 如果依赖方是当前正在加载的插件或其子插件，说明它们在同一 load_plugins 调用链中被导入，
            # 且已在当前上下文中处理过依赖关系。
            continue
        if dep_id == path or dep_id.startswith(path + "."):
            continue
        dep = plugin_service.plugins.get(dep_id)
        if dep is None:
            if not (result := load_plugin(dep_id)):
                referent_set.add(dep_id)
                continue
            publish(Ready(), result.plugin._scope)
            recursive_guard.add(dep_id)
            continue
        if not surface_changed:
            _rebind_dep(dep, path)
            continue
        if _uses_module_level(dep, path):
            _cascade_dep(dep_id, referent_set, recursive_guard)
        else:
            _rebind_dep(dep, path)


class _LoadResult:
    __slots__ = ("_plugin", "_error", "_desc")

    @overload
    def __init__(self, *, plugin: Plugin): ...

    @overload
    def __init__(self, *, error: Exception): ...

    def __init__(self, plugin: Plugin | None = None, error: Exception | None = None):
        if plugin is None and error is None:
            raise ValueError("either plugin or error must be provided")
        if plugin is not None and error is not None:
            raise ValueError("only one of plugin or error can be provided")
        self._plugin = ref(plugin) if plugin is not None else None
        self._desc = repr(plugin) if plugin is not None else "None"
        self._error = error

    @property
    def plugin(self) -> Plugin:
        if self._plugin is None:
            raise RuntimeError("plugin not loaded")
        if plug := self._plugin():
            return plug
        raise RuntimeError("plugin has been garbage collected")

    @property
    def error(self) -> Exception:
        if self._error is None:
            raise RuntimeError("plugin loaded successfully, no error")
        return self._error

    def __bool__(self):
        return self._plugin is not None

    def __repr__(self) -> str:
        return f"<LoadResult plugin={self._desc} error={self._error!r}>"


def load_plugin(
    path: str,
    config: dict | None = None,
    recursive_guard: set[str] | None = None,
    prelude: bool = False,
    staged: bool = False,
) -> _LoadResult:
    """
    以导入路径方式加载模块

    Args:
        path (str): 模块路径
        config (dict): 模块配置
        recursive_guard (set[str]): 递归保护
        prelude (bool): 是否为前置插件
        staged (bool): 是否为暂存加载
    """
    if config is not None:
        config["$path"] = path
    else:
        for k, names in EntariConfig.instance._plugin_names.items():
            if path in names:
                config = EntariConfig.instance.plugin.get(k, {})
                config["$path"] = k
                break
        else:
            config = {"$path": path}
    if prelude:
        config["$static"] = True
    if recursive_guard is None:
        recursive_guard = set()
    path = path.replace("::", "arclet.entari.builtins.")
    if path.startswith(".") and f"${path}" in plugin_service.root.subplugins:
        rootless = plugin_service.plugins[f"${path}"]
        rootless.config = config
        return _LoadResult(plugin=rootless)
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if not staged and (plug := find_plugin(path)):
        plugin_service._direct_plugins.add(plug.path)
        return _LoadResult(plugin=plug)
    try:
        mod = import_plugin(path, config=config, staged=staged)
        if not mod:
            mod = next(
                (
                    import_plugin(_path, config=config, staged=staged)
                    for _path in EntariConfig.instance._plugin_names.get(path, [])
                ),
                None,
            )
        if not mod:
            log.plugin.error(f"cannot found plugin <blue>{path!r}</blue>")
            publish(PluginLoadedFailed(path))
            return _LoadResult(error=RuntimeError("plugin not found"))
        plugin_service._direct_plugins.add(mod.__name__)
        if not staged:
            _handle_dependents(mod.__plugin__, recursive_guard)
        return _LoadResult(plugin=mod.__plugin__)
    except (ImportError, RegisterNotInPluginError, ReusablePluginError, StaticPluginDispatchError) as e:
        return _LoadResult(error=e)
    except Exception as e:
        log.plugin.exception(f"failed to load plugin <blue>{path!r}</blue>: {e}", exc_info=e)
        publish(PluginLoadedFailed(path))
        return _LoadResult(error=e)


def find_plugin(name: str) -> Plugin | None:
    """根据插件名称查找插件"""
    if name in plugin_service.plugins:
        return plugin_service.plugins[name]
    if name in EntariConfig.instance.plugin_prefixes:
        for prefix in EntariConfig.instance.plugin_prefixes[name]:
            if f"{prefix}{name}" in plugin_service.plugins:
                return plugin_service.plugins[f"{prefix}{name}"]
    if not name.count(".") and f"entari_plugin_{name}" in plugin_service.plugins:
        return plugin_service.plugins[f"entari_plugin_{name}"]


def unload_plugin(plugin: str):
    """卸载插件及其子插件"""
    plugin = plugin.replace("::", "arclet.entari.builtins.")
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
    if not (_plugin := find_plugin(plugin)):
        return False
    _plugin.dispose()
    return True


async def unload_plugin_async(plugin: str):
    plugin = plugin.replace("::", "arclet.entari.builtins.")
    while plugin in plugin_service._subplugined:
        plugin = plugin_service._subplugined[plugin]
    if not (_plugin := find_plugin(plugin)):
        return False
    if tasks := _plugin.dispose():
        await asyncio.wait(tasks)
    return True


def _unload_for_reload(plugin_id: str) -> bool:
    """级联重载中的卸载步骤：以 replacing=True 拆卸，与 reload_plugin 的语义一致

    不执行永久卸载的引用/依赖收尾；bindings 随拆卸清理并由随后 load 重新记录。
    """
    if not (_plugin := find_plugin(plugin_id)):
        return False
    _plugin.dispose(replacing=True)
    return True


async def _discard_staged_state(plugin_id: str) -> None:
    """清理异常路径遗留的暂存登记与临时绑定。

    exec_module 的 restore_kept_state 等步骤位于 _abort 之外，异常时暂存插件可能既不 promote 也不 dispose。
    残留的 _staged_bindings 会让之后同 id 的绑定一直写入孤立表。
    这里显式 dispose 暂存插件，让 finalizer 不会因登记已移除而误删同 id 的存活插件；随后再兜底清理绑定键。
    """
    try:
        tasks = set()
        for sid in list(plugin_service._staged):
            if sid != plugin_id and not sid.startswith(f"{plugin_id}."):
                continue
            if (staged := plugin_service._staged.get(sid)) is None:
                continue
            try:
                tasks.update(staged.dispose(replacing=True))
            except Exception as e:
                log.plugin.error(f"failed to discard staged plugin <r>{sid!r}</r>: {e!r}")
        if tasks:
            await asyncio.wait(tasks)
    finally:
        for sid in list(plugin_service._staged_bindings):
            if sid == plugin_id or sid.startswith(f"{plugin_id}."):
                plugin_service._staged_bindings.pop(sid, None)
        # 异常可能发生在子插件登记之后、父插件记录 subplugins 之前，兜底清除孤立归属
        for sid in list(plugin_service._subplugined):
            if (sid == plugin_id or sid.startswith(f"{plugin_id}.")) and sid not in plugin_service.plugins:
                plugin_service._subplugined.pop(sid, None)


def _snapshot_sys_entries(plugin_id: str) -> dict[str, Any]:
    """记录重载前插件前缀下的全部模块登记，失败时用于恢复旧树的 sys.modules 状态"""
    prefix = f"{plugin_id}."
    return {name: entry for name, entry in sys.modules.items() if name == plugin_id or name.startswith(prefix)}


def _restore_sys_entries(plugin_id: str, entries: dict[str, Any]) -> None:
    """恢复旧插件树的模块登记，并清除本次失败加载新建的同前缀条目"""
    prefix = f"{plugin_id}."
    for name in list(sys.modules):
        if (name == plugin_id or name.startswith(prefix)) and name not in entries:
            sys.modules.pop(name, None)
    sys.modules.update(entries)


def _promote_staged_scope(plugin: Plugin, sid: str) -> None:
    """把暂存作用域的 id 从 ``<id>@staging`` 切换为正式插件 id，并更新全局作用域表"""
    scope = plugin._scope
    staging_id = f"{sid}@staging"
    if scope.id != staging_id:
        return
    _scopes.pop(staging_id, None)
    scope.id = sid
    _scopes[sid] = scope


def promote_staged(plugin: Plugin):
    """将暂存插件及其子插件正式注册进 plugin_service，并恢复启用状态与父绑定

    子插件按设计全部平级挂载在顶层插件下，``_subplugined`` 一律指向顶层插件 id；
    父属性写回（插件导入链）使模块中的属性指向新模块对象。
    """
    for sid in [plugin.id, *plugin.subplugins]:
        # replace instead of merge: deleted imports in the new version should not remain in the binding index
        if sid in plugin_service._staged_bindings:
            staged_bindings = plugin_service._staged_bindings.pop(sid)
            if staged_bindings:
                plugin_service.bindings[sid] = staged_bindings
            else:
                plugin_service.bindings.pop(sid, None)
        if staged := plugin_service._staged.pop(sid, None):
            _promote_staged_scope(staged, sid)
            plugin_service.plugins[sid] = staged
            # 提升后不再属于暂存事务，后续 niche 等动态创建应直接进入 plugins
            staged.staged = False
            if sid != plugin.id:
                plugin_service._subplugined[sid] = plugin.id
            staged.check_disable()
            if plugin_service.status.blocking:
                publish(Ready(), staged._scope)
    plugin_service._unloaded.discard(plugin.id)
    for sid in plugin.subplugins:
        if sid not in plugin_service.plugins or sid not in plugin_service._subplugined:
            continue
        parent = plugin_service.plugins.get(plugin_service._subplugined[sid])
        if parent is None:
            continue
        if sid not in parent.subplugins:
            parent.subplugins.append(sid)
        parent.module.__dict__[sid.rpartition(".")[-1]] = plugin_service.plugins[sid].module


def _collect_subtree(plugin: Plugin) -> list[str]:
    """DFS 收集插件树的全部子插件 id（父在前，去重）"""
    ids: list[str] = []
    seen: set[str] = set()

    def walk(plug: Plugin):
        for sid in plug.subplugins:
            if sid in seen:
                continue
            seen.add(sid)
            ids.append(sid)
            if sub := plugin_service.plugins.get(sid):
                walk(sub)

    walk(plugin)
    return ids


async def reload_plugin(path: str, conf: dict | None = None) -> _LoadResult:
    """原子重载：导入失败时旧插件继续运行；成功后处理依赖方"""
    path = path.replace("::", "arclet.entari.builtins.")
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if not (plugin := find_plugin(path)):
        return _LoadResult(error=RuntimeError(f"plugin {path!r} not found"))
    if plugin.is_static:
        return _LoadResult(error=RuntimeError(f"plugin {path!r} is static and cannot be reloaded"))
    _conf = conf if conf is not None else plugin.config.copy()
    old_subplugins = _collect_subtree(plugin)
    old_sys_entries = _snapshot_sys_entries(path)
    for name in old_subplugins:
        sys.modules.pop(name, None)
    log.plugin.debug(f"staged loading <y>{path!r}</y>, old plugin keeps running until swap")
    if not (result := load_plugin(path, _conf, staged=True)):
        await _discard_staged_state(path)
        # stage load will overwrite/delete old sys.modules entries, must restore them on failure,
        # otherwise the old plugin is still running but cannot be re-imported
        _restore_sys_entries(path, old_sys_entries)
        log.plugin.error(f"failed to load staged plugin <blue>{path!r}</blue>, old plugin keeps running")
        return result
    if tasks := plugin.dispose(replacing=True):
        await asyncio.wait(tasks)
    new_plugin = result.plugin
    promote_staged(new_plugin)
    # 恢复未随 staged exec 重新导入的子插件（load_plugins/config 方式加载的模块在
    # 暂存加载期间 load_plugin 上溯命中旧插件早退，且不记入新插件 subplugins）
    for sub_id in old_subplugins:
        if sub_id in new_plugin.subplugins or sub_id in plugin_service.plugins:
            continue
        try:
            mod = import_plugin(sub_id)
        except Exception as e:
            log.plugin.error(f"failed to restore sub-plugin <r>{sub_id!r}</r>: {e!r}")
            continue
        if mod is None:
            log.plugin.error(f"cannot restore sub-plugin <r>{sub_id!r}</r>: module not found")
            continue
        log.plugin.debug(f"restored sub-plugin <y>{sub_id!r}</y> not re-imported by staged reload")
    _handle_dependents(new_plugin)
    return result


async def reload_subplugin(path: str, conf: dict | None = None) -> _LoadResult:
    """子插件粒度重载：仅替换子插件自身，父插件与兄弟经绑定索引重绑

    父插件在模块层使用该子插件名字（基类/模块级装饰器/顶层实例化）→ 回退整树重载；
    子插件自身经暂存机制原子替换（失败时旧子插件继续运行）。
    """
    path = path.replace("::", "arclet.entari.builtins.")
    if path not in plugin_service.plugins or path not in plugin_service._subplugined:
        return _LoadResult(error=RuntimeError(f"sub-plugin {path!r} not found"))
    plugin = plugin_service.plugins[path]
    parent_id = plugin_service._subplugined[path]
    parent = plugin_service.plugins.get(parent_id)
    if parent and _uses_module_level(parent, path):
        log.plugin.debug(f"parent <y>{parent_id!r}</y> uses <y>{path!r}</y> at module level, full tree reload")
        return await reload_plugin(parent_id, parent.config.copy())
    _conf = conf if conf is not None else plugin.config.copy()
    old_sys_entries = _snapshot_sys_entries(path)
    log.plugin.debug(f"staged loading sub-plugin <y>{path!r}</y>, old sub-plugin keeps running until swap")
    try:
        mod = import_plugin(path, config=_conf, staged=True)
    except Exception as e:
        await _discard_staged_state(path)
        _restore_sys_entries(path, old_sys_entries)
        return _LoadResult(error=e)
    if not mod:
        await _discard_staged_state(path)
        _restore_sys_entries(path, old_sys_entries)
        log.plugin.error(f"failed to load staged sub-plugin <blue>{path!r}</blue>, old sub-plugin keeps running")
        return _LoadResult(
            error=RuntimeError(f"failed to load staged sub-plugin {path!r}, old sub-plugin keeps running")
        )
    if tasks := plugin.dispose(replacing=True):
        await asyncio.wait(tasks)
    new_plugin = mod.__plugin__  # type: ignore
    promote_staged(new_plugin)
    _handle_dependents(new_plugin)
    return _LoadResult(plugin=new_plugin)
