import ast
import builtins
import copy
import inspect
import sys
import types
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from arclet.letoderea.scope import scope_ctx

from ..logger import log
from .model import Plugin, PluginInspect, current_plugin


@dataclass(slots=True)
class FunctionChange:
    qualname: str
    ordinal: int
    count: int
    node: ast.FunctionDef | ast.AsyncFunctionDef
    signature_changed: bool
    append: bool = False


def list_dump(nodes: Sequence[ast.AST]) -> str:
    """Copy from ast.py line 167-170"""
    return f"[{', '.join(ast.dump(x, include_attributes=False) for x in nodes)}]"


def iter_functions(body: list[ast.stmt]) -> Iterator[tuple[str, int, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """按 qualname 收集模块顶层函数与类方法（含嵌套类）"""

    def _walk(body: list[ast.stmt], prefix: str) -> Iterator[tuple[str, int, ast.FunctionDef | ast.AsyncFunctionDef]]:
        seen: dict[str, int] = {}
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}{stmt.name}"
                ordinal = seen.get(stmt.name, 0)
                seen[stmt.name] = ordinal + 1
                yield qualname, ordinal, stmt
            elif isinstance(stmt, ast.ClassDef):
                yield from _walk(stmt.body, f"{prefix}{stmt.name}.")

    yield from _walk(body, "")


def _signature_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> set[str]:
    names = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def _comp_targets(gen: ast.comprehension) -> set[str]:
    targets: set[str] = set()
    stack: list[ast.AST] = [gen.target]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Name):
            targets.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            stack.extend(node.elts)
        elif isinstance(node, ast.Starred):
            stack.append(node.value)
    return targets


def _structurally_same(o: ast.stmt, n: ast.stmt) -> bool:
    """结构比较：函数/方法体跳过（由 qualname 配对分析），其余须 dump 相等"""
    if isinstance(o, (ast.FunctionDef, ast.AsyncFunctionDef)) and isinstance(
        n, (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        return True

    if isinstance(o, ast.ClassDef) and isinstance(n, ast.ClassDef):
        if list_dump(o.decorator_list) != list_dump(n.decorator_list):
            return False
        if list_dump(o.bases) != list_dump(n.bases):
            return False
        if list_dump(o.keywords) != list_dump(n.keywords):
            return False
        if len(o.body) != len(n.body):
            return False
        return all(_structurally_same(x, y) for x, y in zip(o.body, n.body))
    return ast.dump(o, include_attributes=False) == ast.dump(n, include_attributes=False)


def _import_names(stmt: ast.stmt) -> dict[str, str]:
    """import 语句绑定的 {名字: 目标模块}"""
    if isinstance(stmt, ast.Import):
        return {alias.asname or alias.name.split(".")[0]: alias.name for alias in stmt.names}
    if isinstance(stmt, ast.ImportFrom):
        module = "." * (stmt.level or 0) + (stmt.module or "")
        return {alias.asname or alias.name: f"{module}.{alias.name}" for alias in stmt.names if alias.name != "*"}
    return {}


def _align_prefix(
    old_body: list[ast.stmt], new_body: list[ast.stmt]
) -> tuple[dict[str, str], dict[str, str], list[tuple[ast.stmt, ast.stmt]], list[ast.stmt]] | None:
    """对齐新旧模块前缀：允许 import 语句就地变化/增删，其余语句须结构相同

    返回 (旧 import 绑定, 新 import 绑定, 对齐的非 import 语句对, 新尾部)。
    None 表示结构无法匹配（需全量重载）。
    """
    old_imports: dict[str, str] = {}
    new_imports: dict[str, str] = {}
    pairs: list[tuple[ast.stmt, ast.stmt]] = []
    i = j = 0
    while i < len(old_body) and j < len(new_body):
        o, n = old_body[i], new_body[j]
        if isinstance(o, (ast.Import, ast.ImportFrom)) and isinstance(n, (ast.Import, ast.ImportFrom)):
            old_imports.update(_import_names(o))
            new_imports.update(_import_names(n))
            i += 1
            j += 1
        elif isinstance(o, (ast.Import, ast.ImportFrom)):
            old_imports.update(_import_names(o))
            i += 1
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            new_imports.update(_import_names(n))
            j += 1
        elif _structurally_same(o, n):
            pairs.append((o, n))
            i += 1
            j += 1
        else:
            return None
    if i != len(old_body):
        return None
    return old_imports, new_imports, pairs, new_body[j:]


def _changed_import_names(old_imports: dict[str, str], new_imports: dict[str, str]) -> set[str]:
    """新旧 import 绑定的变更名集合（新增/移除/改绑）"""
    common = set(old_imports) & set(new_imports)
    return (set(old_imports) ^ set(new_imports)) | {n for n in common if old_imports[n] != new_imports[n]}


class _GlobalNameCollector:
    """作用域感知的名字收集器：收集会在模块全局或 builtins 解析的名字

    规则：Name(Load) 在自身与所有外层函数作用域均未绑定 → 全局名。
    """

    __slots__ = ("used", "stack")

    def __init__(self):
        self.used: set[str] = set()
        self.stack: list[set[str]] = [set()]

    def _bound(self, name: str) -> bool:
        return any(name in scope for scope in self.stack)

    def _bind(self, name: str):
        self.stack[-1].add(name)

    def collect(self, stmts: list[ast.stmt], initial: set[str] | None = None) -> set[str]:
        self.used = set()
        self.stack = [initial or set()]
        for stmt in stmts:
            self.visit_stmt(stmt)
        return self.used

    def visit_expr(self, expr: ast.expr):
        if isinstance(expr, ast.Name):
            if isinstance(expr.ctx, ast.Load) and not self._bound(expr.id):
                self.used.add(expr.id)
            elif isinstance(expr.ctx, ast.Store):
                self._bind(expr.id)
        elif isinstance(expr, ast.Lambda):
            self.stack.append(_signature_names(expr))
            self.visit_expr(expr.body)
            self.stack.pop()
        elif isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            comps = expr.generators
            if comps:
                self.visit_expr(comps[0].iter)
            self.stack.append({name for gen in comps for name in _comp_targets(gen)})
            for gen in comps:
                if gen is not comps[0]:
                    self.visit_expr(gen.iter)
                for cond in gen.ifs:
                    self.visit_expr(cond)
            if isinstance(expr, ast.DictComp):
                self.visit_expr(expr.key)
                self.visit_expr(expr.value)
            else:
                self.visit_expr(expr.elt)
            self.stack.pop()
        else:
            for child in ast.iter_child_nodes(expr):
                if isinstance(child, ast.expr):
                    self.visit_expr(child)
                elif isinstance(child, ast.keyword) and child.value is not None:
                    self.visit_expr(child.value)

    def visit_stmt(self, stmt: ast.stmt):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._bind(stmt.name)
            for dec in stmt.decorator_list:
                self.visit_expr(dec)
            for default in [*stmt.args.defaults, *[d for d in stmt.args.kw_defaults if d]]:
                self.visit_expr(default)
            for arg in stmt.args.posonlyargs + stmt.args.args + stmt.args.kwonlyargs:
                if arg.annotation:
                    self.visit_expr(arg.annotation)
            if stmt.args.vararg and stmt.args.vararg.annotation:
                self.visit_expr(stmt.args.vararg.annotation)
            if stmt.args.kwarg and stmt.args.kwarg.annotation:
                self.visit_expr(stmt.args.kwarg.annotation)
            self.stack.append(_signature_names(stmt))
            for body_stmt in stmt.body:
                self.visit_stmt(body_stmt)
            self.stack.pop()
        elif isinstance(stmt, ast.ClassDef):
            self._bind(stmt.name)
            for dec in stmt.decorator_list:
                self.visit_expr(dec)
            for base in stmt.bases:
                self.visit_expr(base)
            for kw in stmt.keywords:
                self.visit_expr(kw.value)
            self.stack.append(set())
            for body_stmt in stmt.body:
                self.visit_stmt(body_stmt)
            self.stack.pop()
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                self.visit_expr(target)
            self.visit_expr(stmt.value)
        elif isinstance(stmt, ast.AnnAssign):
            self.visit_expr(stmt.target)
            self.visit_expr(stmt.annotation)
            if stmt.value:
                self.visit_expr(stmt.value)
        elif isinstance(stmt, ast.AugAssign):
            self.visit_expr(stmt.target)
            self.visit_expr(stmt.value)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            self.visit_expr(stmt.target)
            self.visit_expr(stmt.iter)
            for body_stmt in [*stmt.body, *stmt.orelse]:
                self.visit_stmt(body_stmt)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                self.visit_expr(item.context_expr)
                if item.optional_vars:
                    self.visit_expr(item.optional_vars)
            for body_stmt in stmt.body:
                self.visit_stmt(body_stmt)
        elif isinstance(stmt, ast.Try) or (sys.version_info >= (3, 11) and isinstance(stmt, ast.TryStar)):
            for body_stmt in [*stmt.body, *stmt.orelse, *stmt.finalbody]:
                self.visit_stmt(body_stmt)
            for handler in stmt.handlers:
                if handler.type:
                    self.visit_expr(handler.type)
                if handler.name:
                    self._bind(handler.name)
                for body_stmt in handler.body:
                    self.visit_stmt(body_stmt)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                self._bind(alias.asname or alias.name.split(".")[0])
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                self._bind(alias.asname or alias.name)
        elif isinstance(stmt, ast.If):
            self.visit_expr(stmt.test)
            for body_stmt in [*stmt.body, *stmt.orelse]:
                self.visit_stmt(body_stmt)
        elif isinstance(stmt, ast.While):
            self.visit_expr(stmt.test)
            for body_stmt in [*stmt.body, *stmt.orelse]:
                self.visit_stmt(body_stmt)
        else:
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, ast.expr):
                    self.visit_expr(child)
                elif isinstance(child, ast.stmt):
                    self.visit_stmt(child)


def _collect_unchanged_references(
    pairs: list[tuple[ast.stmt, ast.stmt]], changes: list[FunctionChange], new_nodes: ast.Module
) -> set[str]:
    """收集未变更代码（顶层语句、类级语句、未变更函数/方法体）引用的全局名"""
    collector = _GlobalNameCollector()
    used: set[str] = set()
    for _, new_stmt in pairs:
        if isinstance(new_stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(new_stmt, ast.ClassDef):
            class_stmts = [s for s in new_stmt.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if class_stmts:
                used |= collector.collect(class_stmts)
            continue
        used |= collector.collect([new_stmt])
    changed_nodes = {c.node for c in changes}
    for _, _, fn in iter_functions(new_nodes.body):
        if fn in changed_nodes:
            continue
        used |= collector.collect(fn.body, _signature_names(fn))
    return used


def classify(old_nodes: ast.Module, new_nodes: ast.Module) -> list[FunctionChange] | None:
    """比较新旧模块的 AST，返回可以热替换的函数列表

    函数配对：先按（名称组, 完整节点 dump 相同）锚定未变化函数（容忍位置交换/重排），
    剩余函数按组内顺序配对比较（容忍原地编辑）；重命名（组键变化）与增删（组内数量不匹配）走全量重载。
    文件底部追加的新函数 走 append 路径（整句执行，含装饰器注册，要求旧 body 是新的结构前缀且尾部新增全为函数定义）。
    前缀中的 import 语句允许就地变化/增删，条件是变更的绑定名不被任何未变更代码引用（否则走全量重载）。

    Returns:
        可就地替换的函数列表，None 表示模块整体需要全量重载
    """
    old_body = old_nodes.body
    new_body = new_nodes.body
    aligned = _align_prefix(old_body, new_body)
    if aligned is None:
        return None
    old_imports, new_imports, pairs, tail = aligned
    if tail and not all(
        isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)) for s in tail
    ):
        return None
    old_groups: dict[str, list[tuple[int, ast.FunctionDef | ast.AsyncFunctionDef]]] = {}
    new_groups: dict[str, list[tuple[int, ast.FunctionDef | ast.AsyncFunctionDef]]] = {}
    for qualname, ordinal, fn in iter_functions([o for o, _ in pairs]):
        old_groups.setdefault(qualname, []).append((ordinal, fn))
    for qualname, ordinal, fn in iter_functions([n for _, n in pairs]):
        new_groups.setdefault(qualname, []).append((ordinal, fn))
    if set(old_groups.keys()) != set(new_groups.keys()):
        return None
    changes: list[FunctionChange] = []
    for qualname, old_list in old_groups.items():
        new_list = new_groups[qualname]
        if len(old_list) != len(new_list):
            return None
        used_old: set[int] = set()
        used_new: set[int] = set()
        for i, (_, o_node) in enumerate(old_list):
            for j, (_, n_node) in enumerate(new_list):
                if (
                    i not in used_old
                    and j not in used_new
                    and ast.dump(o_node, include_attributes=False) == ast.dump(n_node, include_attributes=False)
                ):
                    used_old.add(i)
                    used_new.add(j)
                    break
        rest_old = [old_list[i] for i in range(len(old_list)) if i not in used_old]
        rest_new = [new_list[j] for j in range(len(new_list)) if j not in used_new]
        for (o_ord, o_node), (n_ord, n_node) in zip(rest_old, rest_new):
            if list_dump(n_node.decorator_list) != list_dump(o_node.decorator_list):
                return None
            signature_changed = n_node.__class__ is not o_node.__class__ or ast.dump(
                n_node.args, include_attributes=False
            ) != ast.dump(o_node.args, include_attributes=False)
            # if signature_changed or list_dump(n_node.body) != list_dump(o_node.body):
            changes.append(FunctionChange(qualname, o_ord, len(old_list), n_node, signature_changed))
    for stmt in tail:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            changes.append(FunctionChange(stmt.name, 0, 1, stmt, signature_changed=False, append=True))
    if changed_import_names := _changed_import_names(old_imports, new_imports):
        used = _collect_unchanged_references(pairs, changes, new_nodes)
        if changed_import_names & used:
            log.plugin.debug(
                f"changed import names {sorted(changed_import_names & used)!r} are referenced "
                f"by unchanged code, fallback to full reload"
            )
            return None
    return changes


def collect_global_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """收集新函数体中所有会在模块全局或 builtins 解析的名字（含嵌套函数）"""
    collector = _GlobalNameCollector()
    return collector.collect(fn.body, initial=_signature_names(fn))


def _unwrap_fn(target: Any) -> types.FunctionType | None:
    """从模块/类绑定或 Subscriber 中取出裸函数对象"""
    if isinstance(target, types.FunctionType):
        return target
    if isinstance(target, (classmethod, staticmethod)):
        inner = target.__func__
        return inner if isinstance(inner, types.FunctionType) else None
    if hasattr(target, "callable_target"):
        inner = getattr(target, "callable_target")
        return inner if isinstance(inner, types.FunctionType) else None
    return None


def _resolve_old_fn(plugin: Plugin, qualname: str, ordinal: int, count: int) -> types.FunctionType | None:
    """按 (qualname, 序号) 解析活模块中的旧函数对象；返回 None 表示不可就地替换

    最后一个同名定义经模块/类绑定解析（模块执行时同名后者胜出）；
    非最后一个同名定义只能经插件 scope 的 Subscriber 按名字+注册序解析
    （即 `_` 惯用法：多个 `@plugin.listen` 装饰的同名函数）。
    """
    module = plugin.module
    parts = qualname.split(".")
    if len(parts) > 1:
        if ordinal != count - 1:
            return None
        parent = module.__dict__.get(parts[0])
        if parent is None:
            return None
        for part in parts[1:-1]:
            parent = inspect.getattr_static(parent, part, None)
            if parent is None:
                return None
        return _unwrap_fn(inspect.getattr_static(parent, parts[-1], None))
    if ordinal == count - 1:
        return _unwrap_fn(module.__dict__.get(parts[0]))
    candidates = [
        slot.subscriber.callable_target
        for slot in plugin._scope.subscribers
        if isinstance(slot.subscriber.callable_target, types.FunctionType)
        and slot.subscriber.callable_target.__name__ == parts[0]
    ]
    if len(candidates) != count:
        return None
    return candidates[ordinal]


def _build_new_fn(new_node: ast.FunctionDef | ast.AsyncFunctionDef, module: ModuleType) -> types.FunctionType | None:
    """剥掉装饰器后在临时命名空间执行新函数定义，返回新函数对象"""
    node = copy.deepcopy(new_node)
    node.decorator_list = []
    ast.fix_missing_locations(node)
    try:
        code = compile(
            ast.Module(body=[node], type_ignores=[]),
            module.__name__,
            "exec",
            dont_inherit=True,
            optimize=-1,
        )
        ns = dict(module.__dict__)
        exec(code, ns)
    except Exception as e:
        log.plugin.error(f"failed to build new function <blue>{node.name!r}</blue>: {e!r}")
        return None
    fn = ns.get(node.name)
    return fn if isinstance(fn, types.FunctionType) else None


def _decorator_global_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """装饰器表达式中的全局引用（append 路径整句执行时需解析）"""
    used: set[str] = set()
    for dec in node.decorator_list:
        for name in ast.walk(dec):
            if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Load):
                used.add(name.id)
    return used


def _exec_imports(plugin: Plugin, nodes: ast.Module) -> bool:
    """将新源码中的 import 语句按源码顺序执行并写入模块中"""
    module = plugin.module
    for stmt in nodes.body:
        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        stmt_cp = copy.deepcopy(stmt)
        ast.fix_missing_locations(stmt_cp)
        code = compile(
            ast.Module(body=[stmt_cp], type_ignores=[]),
            module.__name__,
            "exec",
            dont_inherit=True,
            optimize=-1,
        )
        try:
            exec(code, module.__dict__)
        except Exception as e:
            log.plugin.error(f"failed to exec import statement at line {stmt.lineno}: {e!r}")
            return False
    return True


def _exec_append(plugin: Plugin, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """在插件上下文（current_plugin + scope）中整句执行新增语句，完成装饰器注册"""
    module = plugin.module
    stmt = copy.deepcopy(node)
    ast.fix_missing_locations(stmt)
    code = compile(
        ast.Module(body=[stmt], type_ignores=[]),
        module.__name__,
        "exec",
        dont_inherit=True,
        optimize=-1,
    )
    token = current_plugin.set(plugin)
    try:
        if not plugin.is_static:
            token1 = scope_ctx.set(plugin._scope)
            try:
                exec(code, module.__dict__)
            finally:
                scope_ctx.reset(token1)
        else:
            exec(code, module.__dict__)
    finally:
        current_plugin.reset(token)
    return True


def swap_functions(plugin: Plugin, new_nodes: ast.Module, changes: list[FunctionChange]) -> bool:
    """就地替换函数实现，如果会影响插件自身或下游依赖方则返回 False，调用方走全量重载"""
    module = plugin.module
    import_names = {
        name
        for stmt in new_nodes.body
        if isinstance(stmt, (ast.Import, ast.ImportFrom))
        for name in _import_names(stmt)
    }
    resolved: list[tuple[types.FunctionType, types.FunctionType, FunctionChange]] = []
    for change in changes:
        new_fn = change.node
        free_names = collect_global_names(new_fn)
        missing = {
            name
            for name in free_names
            if name not in module.__dict__ and name not in vars(builtins) and name not in import_names
        }
        if missing:
            log.plugin.warning(
                f"cannot hot-swap <blue>{change.qualname!r}</blue>: free names {missing!r} missing, "
                "fallback to full reload"
            )
            return False
        if change.append:
            free_names |= _decorator_global_names(new_fn)
            missing = {
                name
                for name in free_names
                if name not in module.__dict__ and name not in vars(builtins) and name not in import_names
            }
            if missing:
                log.plugin.warning(
                    f"cannot append <blue>{change.qualname!r}</blue>: free names {missing!r} missing, "
                    "fallback to full reload"
                )
                return False
            continue
        old_fn = _resolve_old_fn(plugin, change.qualname, change.ordinal, change.count)
        if old_fn is None:
            log.plugin.warning(f"cannot resolve <blue>{change.qualname!r}</blue> in module, fallback to full reload")
            return False
        if change.signature_changed:
            from ..command import _commands

            if any(sub.callable_target is old_fn for sub in _commands.subscribers.values()):
                log.plugin.warning(
                    f"signature of command target <blue>{change.qualname!r}</blue> changed, " "fallback to full reload"
                )
                return False
        new_function = _build_new_fn(new_fn, module)
        if new_function is None:
            return False
        resolved.append((old_fn, new_function, change))
    if not _exec_imports(plugin, new_nodes):
        return False
    for old_fn, new_function, change in resolved:
        old_fn.__code__ = new_function.__code__
        old_fn.__defaults__ = new_function.__defaults__
        old_fn.__kwdefaults__ = new_function.__kwdefaults__
        old_fn.__annotations__ = new_function.__annotations__
        if old_fn.__qualname__ != "_":
            plugin.module.__dict__[old_fn.__qualname__] = new_function
        if change.signature_changed:
            for slot in plugin._scope.subscribers:
                sub = slot.subscriber
                if sub.callable_target is old_fn:
                    sub.callable_target = new_function
                    try:
                        sub._recompile()
                    except Exception as e:
                        log.plugin.error(f"failed to recompile subscriber of <blue>{change.qualname!r}</blue>: {e!r}")
    for change in changes:
        if change.append:
            try:
                _exec_append(plugin, change.node)
            except Exception as e:
                log.plugin.error(f"failed to append <blue>{change.qualname!r}</blue>: {e!r}")
                return False
    plugin._inspect = PluginInspect(new_nodes, ast.dump(new_nodes, include_attributes=False))
    return True
