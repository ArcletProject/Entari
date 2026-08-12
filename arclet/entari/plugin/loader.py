import ast
import asyncio
import sys
from typing import Any

from arclet.letoderea import publish

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
    bound = {name for name, (target, _) in plugin.bindings.items() if target == path or target.startswith(path + ".")}
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
    for name, (target, attr) in plugin.bindings.items():
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
            parent_chain = plugin_service.bindings[parent_pkg]
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


def dependents_of(path: str) -> list[str]:
    """path（及其子树）的依赖方插件：直接导入者 + 经父包再导出链一层（F5）

    子树匹配使整树重载时，依赖子插件的下游插件同样被处理（子插件随树重建，绑定需重绑/级联）。
    插件（或其子模块）对自身子树的绑定属内部边，不构成依赖方，直接跳过。
    """
    parent_pkg = path.rpartition(".")[0]
    result: list[str] = []
    for plug_id, bindings in plugin_service.bindings.items():
        if plug_id == path or plug_id.startswith(path + "."):
            continue
        for name, (target, attr) in bindings.items():
            if target == path or target.startswith(path + "."):
                result.append(plug_id)
                break
            if parent_pkg and attr is not None and target == parent_pkg and parent_pkg in plugin_service.bindings:
                parent_chain = plugin_service.bindings[parent_pkg]
                if parent_chain.get(attr or name, (None, None))[0] == path:
                    result.append(plug_id)
                    break
    return result


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
    unload_plugin(dep_id)
    if not (plug := load_plugin(dep_id)):
        referent_set.add(dep_id)
    else:
        publish(Ready(), plug._scope)
        recursive_guard.add(dep_id)


def topo_dependents(dependents: set[str]) -> list[str]:
    """依赖方按 references 图拓扑排序：被依赖者先于依赖者重载

    依赖者 C（`from B import x`）若在 B 之前级联，会绑定旧 B，随后 B 重载时, C 已在 recursive_guard 中被跳过 → 静默。
    拓扑序保证 B 先重载。
    """
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(dep_id: str):
        if dep_id in visited:
            return
        visited.add(dep_id)
        for ref in plugin_service.references.get(dep_id, ()):
            if ref in dependents:
                visit(ref)
        ordered.append(dep_id)

    for dep_id in sorted(dependents):
        visit(dep_id)
    return ordered


def _handle_dependents(plugin: Plugin, recursive_guard: set[str] | None = None):
    """插件完成（重）加载后处理依赖方：公开面未变 → 全部重绑；否则按模块层使用细粒度重绑或级联

    依赖方 = referents 图与绑定索引的并集；公开面指纹未变时新对象与旧对象行为等价，模块层绑定无需重执行；
    指纹变化时仅模块层使用方升级全量，惰性依赖方重绑即可。
    """
    if recursive_guard is None:
        recursive_guard = set()
    path = plugin.path
    dependents = set(plugin_service.referents.get(path, ())) | set(dependents_of(path))
    if not dependents:
        return
    surface_changed = _fingerprint_changed(plugin)
    referent_set = plugin_service.referents.setdefault(path, set())
    current = current_plugin.get(None)
    for dep_id in topo_dependents(dependents):
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
            if not (plug := load_plugin(dep_id)):
                referent_set.add(dep_id)
                continue
            publish(Ready(), plug._scope)
            recursive_guard.add(dep_id)
            continue
        if not surface_changed:
            _rebind_dep(dep, path)
            continue
        if _uses_module_level(dep, path):
            _cascade_dep(dep_id, referent_set, recursive_guard)
        else:
            _rebind_dep(dep, path)


def load_plugin(
    path: str,
    config: dict | None = None,
    recursive_guard: set[str] | None = None,
    prelude: bool = False,
    staged: bool = False,
) -> Plugin | None:
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
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if path in plugin_service._apply:
        if path in plugin_service.plugins:
            return plugin_service.plugins[path]
        log.plugin.trace(f"loaded rootless plugin <y>{path!r}</y>")
        return plugin_service._apply[path][0](config)
    if not staged and (plug := find_plugin(path)):
        plugin_service._direct_plugins.add(plug.path)
        return plug
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
            return
        plugin_service._direct_plugins.add(mod.__name__)
        if not staged:
            _handle_dependents(mod.__plugin__, recursive_guard)
        return mod.__plugin__
    except (ImportError, RegisterNotInPluginError, ReusablePluginError, StaticPluginDispatchError):
        return
    except Exception as e:
        log.plugin.exception(f"failed to load plugin <blue>{path!r}</blue>: {e}", exc_info=e)
        publish(PluginLoadedFailed(path))
        return


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


def promote_staged(plugin: Plugin):
    """将暂存插件及其子插件正式注册进 plugin_service，并恢复启用状态与父绑定

    子插件按加载顺序已记入父插件 subplugins 列表；
    父属性写回（插件导入链）使模块中的属性指向新模块对象。
    """
    for sid in [plugin.id, *plugin.subplugins]:
        if staged := plugin_service._staged.pop(sid, None):
            plugin_service.plugins[sid] = staged
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
        if parent is not None:
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


async def reload_plugin(path: str, conf: dict | None = None) -> bool:
    """原子重载：导入失败时旧插件继续运行；成功后处理依赖方"""
    path = path.replace("::", "arclet.entari.builtins.")
    while path in plugin_service._subplugined:
        path = plugin_service._subplugined[path]
    if not (plugin := find_plugin(path)):
        return False
    if plugin.is_static:
        return False
    _conf = conf if conf is not None else plugin.config.copy()
    old_subplugins = _collect_subtree(plugin)
    for name in old_subplugins:
        sys.modules.pop(name, None)
    log.plugin.debug(f"staged loading <y>{path!r}</y>, old plugin keeps running until swap")
    if not (new_plugin := load_plugin(path, _conf, staged=True)):
        log.plugin.error(f"failed to load staged plugin <blue>{path!r}</blue>, old plugin keeps running")
        return False
    if tasks := plugin.dispose():
        await asyncio.wait(tasks)
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
    return True


async def reload_subplugin(path: str, conf: dict | None = None) -> bool:
    """子插件粒度重载：仅替换子插件自身，父插件与兄弟经绑定索引重绑

    父插件在模块层使用该子插件名字（基类/模块级装饰器/顶层实例化）→ 回退整树重载；
    子插件自身经暂存机制原子替换（失败时旧子插件继续运行）。
    """
    path = path.replace("::", "arclet.entari.builtins.")
    if path not in plugin_service.plugins or path not in plugin_service._subplugined:
        return False
    plugin = plugin_service.plugins[path]
    parent_id = plugin_service._subplugined[path]
    parent = plugin_service.plugins.get(parent_id)
    if parent and _uses_module_level(parent, path):
        log.plugin.debug(f"parent <y>{parent_id!r}</y> uses <y>{path!r}</y> at module level, full tree reload")
        return await reload_plugin(parent_id, parent.config.copy())
    _conf = conf if conf is not None else plugin.config.copy()
    log.plugin.debug(f"staged loading sub-plugin <y>{path!r}</y>, old sub-plugin keeps running until swap")
    if not (mod := import_plugin(path, config=_conf, staged=True)):
        log.plugin.error(f"failed to load staged sub-plugin <blue>{path!r}</blue>, old sub-plugin keeps running")
        return False
    if tasks := plugin.dispose():
        await asyncio.wait(tasks)
    new_plugin = mod.__plugin__  # type: ignore
    promote_staged(new_plugin)
    _handle_dependents(new_plugin)
    return True
