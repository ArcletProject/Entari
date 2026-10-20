from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NamedTuple

from arclet.letoderea import es
from launart import Launart, Service
from launart.status import Phase
from launart.utilles import RequirementResolveFailed, resolve_requirements

from ..event.lifespan import Cleanup, Ready, Startup
from ..event.plugin import PluginUnloaded
from ..logger import log

if TYPE_CHECKING:
    from .model import KeepingVariable, Plugin


class Binding(NamedTuple):
    """一条名字级 import 绑定"""

    name: str
    target: str
    attr: str | None
    last: bool
    """是否为该名字的最后一次绑定（即当前在模块中生效的绑定）"""


class ServiceWaiters:
    def __init__(self):
        self._futures: dict[str, asyncio.Future] = {}

    def assign(self, service_id: str):
        if service_id not in self._futures:
            self._futures[service_id] = asyncio.Future()
        self._futures[service_id].set_result(True)

    def clear(self, service_id: str):
        if service_id in self._futures:
            future = self._futures.pop(service_id)
            if not future.done():
                future.set_result(True)

    async def wait_for(self, service_id: str):
        if service_id not in self._futures:
            self._futures[service_id] = asyncio.Future()
        await self._futures[service_id]


class PluginManagerService(Service):
    id = "entari.plugin.manager"

    plugins: dict[str, Plugin]
    """插件字典，键为插件ID，值为插件对象"""
    referents: dict[str, set[str]]
    """插件引用字典，键为插件ID，值为引用该插件的其他插件ID集合"""
    references: dict[str, set[str]]
    """插件被引用字典，键为插件ID，值为该插件引用的其他插件ID集合"""
    bindings: dict[str, list[Binding]]
    """插件导入绑定字典，键为插件ID，值为该插件全部导入边。同名多次绑定时均保留，仅 last=True 的为当前生效绑定"""
    _staged_bindings: dict[str, list[Binding]]
    """暂存插件的导入绑定，键为插件ID；promote_staged 时整体替换 bindings 中同 id 的记录"""
    fingerprints: dict[str, str]
    """插件指纹字典，键为插件ID，值为该插件的指纹字符串"""
    service_waiter: ServiceWaiters
    _keep_values: dict[str, dict[str, KeepingVariable]]
    _direct_plugins: set[str]
    """直接插件集合，存储所有直接加载（反过来即只由插件导入的插件）的插件ID"""
    _unloaded: set[str]
    """卸载插件集合，存储所有已卸载的插件ID"""
    _subplugined: dict[str, str]
    """子插件字典，键为子插件ID，值为父插件ID"""
    _staged: dict[str, Plugin]
    """插件暂存"""
    root: Plugin
    """根插件对象，作为基础插件的父插件"""

    def __init__(self):
        super().__init__()
        self.plugins = {}
        self._direct_plugins = set()
        self._keep_values = {}
        self.referents = {}
        self.references = {}
        self._unloaded = set()
        self._subplugined = {}
        self.bindings = {}
        self._staged_bindings = {}
        self.fingerprints = {}
        self._staged = {}
        self.service_waiter = ServiceWaiters()

    @property
    def required(self) -> set[str]:
        return {"entari.service"}

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "cleanup", "blocking"}

    def last_bindings(self, pid: str) -> dict[str, tuple[str, str | None]]:
        """插件当前生效的绑定视图 {名字: (目标模块, 属性)}（每个名字仅取最后一次绑定）"""
        return {b.name: (b.target, b.attr) for b in self.bindings.get(pid, ()) if b.last}

    def dependents_of(self, path: str, ensure: bool = True) -> list[str]:
        """path（及其子树）的依赖方插件：直接导入者 + 经父包再导出链一层

        子树匹配使整树重载时，依赖子插件的下游插件同样被处理（子插件随树重建，绑定需重绑/级联）。
        插件（或其子模块）对自身子树的绑定属内部边，不构成依赖方，直接跳过。

        Args:
            path (str): 插件ID或其子模块路径
            ensure (bool, optional): 是否确保返回的插件ID存在于已加载插件中. Defaults to True.

        Returns:
            list[str]: 依赖方插件ID列表
        """
        parent_pkg = path.rpartition(".")[0]
        result: list[str] = []
        for plug_id, edges in self.bindings.items():
            if plug_id == path or plug_id.startswith(path + "."):
                continue
            for name, target, attr, _ in edges:
                if target == path or target.startswith(path + "."):
                    result.append(plug_id)
                    break
                if parent_pkg and attr is not None and target == parent_pkg and parent_pkg in self.bindings:
                    parent_chain = self.last_bindings(parent_pkg)
                    if parent_chain.get(attr or name, (None, None))[0] == path:
                        result.append(plug_id)
                        break
        if ensure:
            result = [r for r in result if r in self.plugins]
        return result

    def topo_dependents(self, dependents: set[str]) -> list[str]:
        """依赖方按 references 图拓扑排序：上游（被依赖者）优先于下游（依赖者）

        依赖者 C 若在 B 之前级联，会绑定旧 B，随后 B 重载时, C 已在 recursive_guard 中被跳过 → 静默。
        拓扑序保证 B 先重载。
        """
        ordered: list[str] = []
        visited: set[str] = set()

        def visit(dep_id: str):
            if dep_id in visited:
                return
            visited.add(dep_id)
            for ref in self.references.get(dep_id, ()):
                if ref in dependents:
                    visit(ref)
            ordered.append(dep_id)

        for dep_id in sorted(dependents):
            visit(dep_id)
        return ordered

    async def launch(self, manager: Launart):

        servs = []
        servs_map = {}

        for plug in self.plugins.values():
            if tasks := plug.check_disable():
                await asyncio.wait(tasks)
            else:
                for serv in plug._services.values():
                    servs.append(serv)
                    servs_map[serv.id] = plug.id
        try:
            results = resolve_requirements(servs)
        except RequirementResolveFailed as e:
            unresolved = "\n".join(f"  - <y>{serv.id}</y> (required: {', '.join(serv.required)})" for serv in e.args[0])
            log.plugin.error(
                f"failed to resolve service requirements, maybe caused by circular dependencies or missing services:"
                f"\n{unresolved}"
            )
            return
        for layer in results:
            for serv in layer:
                manager.add_component(serv)
                self.service_waiter.assign(serv.id)

        async with self.stage("preparing"):
            es.publish(Startup())
        async with self.stage("blocking"):
            for plug in self.plugins.values():
                if not plug._apply:
                    continue
                plug.exec_apply()
                if tasks := plug.check_disable():
                    await asyncio.wait(tasks)
            es.publish(Ready())
            await manager.status.wait_for_sigexit()
        async with self.stage("cleanup"):
            es.publish(Cleanup())
            ids = [k for k in self.plugins.keys() if k not in self._subplugined]
            for plug_id in reversed(ids):
                plug = self.plugins[plug_id]
                try:
                    await es.publish(PluginUnloaded(plug.id))
                    if tasks := plug.dispose(is_cleanup=True):
                        await asyncio.wait(tasks)
                except Exception as e:
                    log.plugin.error(f"failed to dispose plugin <y>{plug.id}</y> caused by {e!r}")
                    self.plugins.pop(plug_id, None)
            for values in self._keep_values.values():
                for value in values.values():
                    await value.dispose()
                values.clear()
            self._keep_values.clear()


plugin_service = PluginManagerService()
