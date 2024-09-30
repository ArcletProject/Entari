import ast
from collections.abc import Sequence
from importlib import _bootstrap  # type: ignore
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder, SourceFileLoader
from importlib.util import module_from_spec, resolve_name
import sys
from types import ModuleType
from typing import Optional

from .model import Plugin, PluginMetadata, _current_plugin
from .service import service

_SUBMODULE_WAITLIST: dict[str, set[str]] = {}


def package(*names: str):
    """手动指定特定模块作为插件的子模块"""
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    _SUBMODULE_WAITLIST.setdefault(plugin.module.__name__, set()).update(names)


def _unpack_import_from(__fullname: str, mod: str, aliases: list[str]):
    if mod == ".":
        return tuple(import_plugin(f".{alias}", __fullname) for alias in aliases)
    _mod = import_plugin(f".{mod}", __fullname) if mod else import_plugin(__fullname)
    return tuple(getattr(_mod, alias) for alias in aliases)


class PluginLoader(SourceFileLoader):
    def __init__(self, fullname: str, path: str, parent_plugin_id: Optional[str] = None) -> None:
        self.loaded = False
        self.parent_plugin_id = parent_plugin_id
        super().__init__(fullname, path)

    def source_to_code(self, data, path, *, _optimize=-1):  # type: ignore
        """Return the code object compiled from source.

        The 'data' argument can be any object type that compile() supports.
        """
        nodes = ast.parse(data, type_comments=True)
        for i, body in enumerate(nodes.body):
            if isinstance(body, ast.ImportFrom):
                if body.level == 0 and (
                    body.module in _SUBMODULE_WAITLIST.get(self.name, ()) or body.module in service.plugins
                ):
                    aliases = [alias.asname or alias.name for alias in body.names]
                    nodes.body[i] = ast.parse(
                        ",".join(aliases)
                        + f"=__unpack_import_from('{self.name}', '', {[alias.name for alias in body.names]!r})"
                    ).body[0]
                    nodes.body[i].lineno = body.lineno
                    nodes.body[i].end_lineno = body.end_lineno
                if body.level == 1:
                    if body.module is None:
                        aliases = [alias.asname or alias.name for alias in body.names]
                        nodes.body[i] = ast.parse(
                            ",".join(aliases)
                            + f"=__unpack_import_from('{self.name}', '.', {[alias.name for alias in body.names]!r})"
                        ).body[0]
                        nodes.body[i].lineno = body.lineno
                        nodes.body[i].end_lineno = body.end_lineno
                    else:
                        aliases = [alias.asname or alias.name for alias in body.names]
                        nodes.body[i] = ast.parse(
                            ",".join(aliases)
                            + (
                                f"=__unpack_import_from('{self.name}', {body.module!r}, "
                                f"{[alias.name for alias in body.names]!r})"
                            )
                        ).body[0]
                        nodes.body[i].lineno = body.lineno
                        nodes.body[i].end_lineno = body.end_lineno
            elif (
                isinstance(body, ast.Expr)
                and isinstance(body.value, ast.Call)
                and isinstance(body.value.func, ast.Name)
                and body.value.func.id == "package"
            ):
                if body.value.args and isinstance(body.value.args[0], ast.Constant):
                    _SUBMODULE_WAITLIST.setdefault(self.name, set()).update(arg.value for arg in body.value.args)  # type: ignore
            elif isinstance(body, ast.Import):
                aliases = [alias.asname or alias.name for alias in body.names]
                nodes.body[i] = ast.parse(
                    ",".join(aliases)
                    + "="
                    + ",".join(
                        (
                            f"__import_plugin({alias.name!r})"
                            if (alias.name in _SUBMODULE_WAITLIST.get(self.name, ()) or alias.name in service.plugins)
                            else f"__import__({alias.name!r})"
                        )
                        for alias in body.names
                    )
                ).body[0]
                nodes.body[i].lineno = body.lineno
                nodes.body[i].end_lineno = body.end_lineno
        return _bootstrap._call_with_frames_removed(compile, nodes, path, "exec", dont_inherit=True, optimize=_optimize)

    def create_module(self, spec) -> Optional[ModuleType]:
        if self.name in service.plugins:
            self.loaded = True
            return service.plugins[self.name].module
        return super().create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        if plugin := _current_plugin.get(service.plugins.get(self.parent_plugin_id) if self.parent_plugin_id else None):
            if module.__name__ == plugin.module.__name__:  # from . import xxxx
                return
            setattr(module, "__plugin__", plugin)
            setattr(module, "__unpack_import_from", _unpack_import_from)
            setattr(module, "__import_plugin", import_plugin)
            try:
                super().exec_module(module)
            except Exception:
                delattr(module, "__plugin__")
                raise
            else:
                plugin.submodules[module.__name__] = module
            return

        if self.loaded:
            return

        # create plugin before executing
        plugin = Plugin(module.__name__, module)
        setattr(module, "__plugin__", plugin)
        setattr(module, "__unpack_import_from", _unpack_import_from)
        setattr(module, "__import_plugin", import_plugin)

        # enter plugin context
        _plugin_token = _current_plugin.set(plugin)

        try:
            super().exec_module(module)
        except Exception:
            plugin.dispose()
            raise
        finally:
            # leave plugin context
            _current_plugin.reset(_plugin_token)

        # get plugin metadata
        metadata: Optional[PluginMetadata] = getattr(module, "__plugin_metadata__", None)
        if metadata and not plugin.metadata:
            plugin._metadata = metadata
        return


def find_spec(name, package=None):
    fullname = resolve_name(name, package) if name.startswith(".") else name
    parent_name = fullname.rpartition(".")[0]
    if parent_name:
        if parent_name in service.plugins:
            parent = service.plugins[parent_name].module
        else:
            parent = __import__(parent_name, fromlist=["__path__"])
        try:
            parent_path = parent.__path__
        except AttributeError as e:
            raise ModuleNotFoundError(
                f"__path__ attribute not found on {parent_name!r} " f"while trying to find {fullname!r}",
                name=fullname,
            ) from e
    else:
        parent_path = None
    module_spec = PathFinder.find_spec(fullname, parent_path, None)
    if not module_spec:
        return
    module_origin = module_spec.origin
    if not module_origin:
        return
    module_spec.loader = PluginLoader(fullname, module_origin)
    return module_spec


def import_plugin(name, package=None):
    spec = find_spec(name, package)
    if spec:
        mod = module_from_spec(spec)
        if spec.loader:
            spec.loader.exec_module(mod)
        return mod
    return


class _PluginFinder(MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[ModuleType] = None,
    ):
        module_spec = PathFinder.find_spec(fullname, path, target)
        if not module_spec:
            return
        module_origin = module_spec.origin
        if not module_origin:
            return
        if plug := _current_plugin.get(None):
            if plug.module.__spec__ and plug.module.__spec__.origin == module_spec.origin:
                return plug.module.__spec__
            if module_spec.parent and module_spec.parent == plug.module.__name__:
                module_spec.loader = PluginLoader(fullname, module_origin, plug.id)
                return module_spec
            elif module_spec.name in _SUBMODULE_WAITLIST[plug.module.__name__]:
                module_spec.loader = PluginLoader(fullname, module_origin, plug.id)
                # _SUBMODULE_WAITLIST[plug.module.__name__].remove(module_spec.name)
                return module_spec

        if module_spec.name in service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin)
            return module_spec
        for plug in service.plugins.values():
            if module_spec.name in plug.submodules:
                module_spec.loader = PluginLoader(fullname, module_origin, plug.id)
                return module_spec
        return


sys.meta_path.insert(0, _PluginFinder())
