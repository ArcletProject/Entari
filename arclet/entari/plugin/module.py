import ast
from collections.abc import Sequence
from importlib import _bootstrap, _bootstrap_external  # type: ignore
from importlib.abc import MetaPathFinder
from importlib.machinery import ExtensionFileLoader, PathFinder, SourceFileLoader
from importlib.util import module_from_spec, resolve_name
from io import BytesIO
import re
import sys
import tokenize
from types import ModuleType
from typing import Optional

from arclet.letoderea.scope import scope_ctx

from ..config import EntariConfig
from ..logger import log
from .model import Plugin, PluginMetadata, _current_plugin
from .service import plugin_service

_SUBMODULE_WAITLIST: dict[str, set[str]] = {}
_ENSURE_IS_PLUGIN: set[str] = set()
_IMPORTING = set()

PLUGIN_PAT = re.compile(r"entari:\s*plugin")
SUBPLUGIN_PAT = re.compile(r"entari:\s*(?:package|subplugin)")


def package(*names: str):
    """手动指定特定模块作为插件的子模块"""
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    _SUBMODULE_WAITLIST.setdefault(plugin.module.__name__, set()).update(names)


def requires(*names: str):
    """手动指定哪些模块是插件"""
    _ENSURE_IS_PLUGIN.update(name.replace("::", "arclet.entari.builtins.") for name in names)


def _ensure_plugin(names: list[str], sub: bool, current: str, prefix=""):
    for name in names:
        if sub:
            _SUBMODULE_WAITLIST.setdefault(current, set()).add(f"{prefix}{name}")
        else:
            _ENSURE_IS_PLUGIN.add(f"{prefix}{name}")
        plugin_service.referents.setdefault(f"{prefix}{name}", set()).add(current)
        plugin_service.references.setdefault(current, set()).add(f"{prefix}{name}")
        _IMPORTING.add(f"{prefix}{name}")


class PluginLoader(SourceFileLoader):
    def __init__(self, fullname: str, path: str, parent_plugin_id: Optional[str] = None) -> None:
        self.loaded = False
        self.parent_plugin_id = parent_plugin_id
        super().__init__(fullname, path)

    def get_code(self, fullname):
        """Concrete implementation of InspectLoader.get_code.

        Reading of bytecode requires path_stats to be implemented. To write
        bytecode, set_data must also be implemented.

        """
        source_path = self.get_filename(fullname)
        source_bytes = None
        if source_bytes is None:
            source_bytes = self.get_data(source_path)
        code_object = self.source_to_code(source_bytes, source_path)
        return code_object

    def source_to_code(self, data, path="<string>"):
        """Return the code object compiled from source.

        The 'data' argument can be any object type that compile() supports.
        """
        if not isinstance(data, bytes):
            return _bootstrap._call_with_frames_removed(  # type: ignore
                compile, data, path, "exec", dont_inherit=True, optimize=-1
            )
        name = self.name
        signed_plugin_lineno = []
        signed_subplugin_lineno = []
        for token in tokenize.tokenize(BytesIO(data).readline):
            if token.type == tokenize.COMMENT:
                if PLUGIN_PAT.search(token.string):
                    signed_plugin_lineno.append(token.start[0])
                elif SUBPLUGIN_PAT.search(token.string):
                    signed_subplugin_lineno.append(token.start[0])

        try:
            nodes = ast.parse(data, type_comments=True)
        except SyntaxError:
            return _bootstrap._call_with_frames_removed(  # type: ignore
                compile, data, path, "exec", dont_inherit=True, optimize=-1
            )
        for body in ast.walk(nodes):
            if isinstance(body, ast.ImportFrom):
                if body.module is None:  # from . import xxx
                    _ensure_plugin(
                        [alias.name for alias in body.names], body.lineno not in signed_plugin_lineno, name, f"{name}."
                    )
                elif body.level == 0 and body.module not in (
                    *sys.builtin_module_names,
                    *getattr(sys, "stdlib_module_names", []),
                ):  # from xxx import xxx
                    if body.lineno in signed_plugin_lineno:
                        _ensure_plugin([body.module], False, name)
                    if body.lineno in signed_subplugin_lineno:
                        _ensure_plugin([body.module], True, name)
                elif body.level == 1:  # from .xxx import xxx
                    prefix = f"{name}." if path.endswith("__init__.py") else name.rpartition(".")[0] + "."
                    _ensure_plugin([body.module], True, name, f"{prefix}.")
                else:  # from ..xxx import xxx
                    prefix = ".".join(
                        name.split(".")[: -body.level + 1 if path.endswith("__init__.py") else -body.level]
                    )
                    _ensure_plugin([body.module], body.lineno not in signed_plugin_lineno, name, f"{prefix}.")
            elif isinstance(body, ast.Import):
                if body.lineno in signed_plugin_lineno:
                    _ensure_plugin([alias.name for alias in body.names], False, name)
                if body.lineno in signed_subplugin_lineno:
                    _ensure_plugin([alias.name for alias in body.names], True, name)

        return _bootstrap._call_with_frames_removed(  # type: ignore
            compile, nodes, path, "exec", dont_inherit=True, optimize=-1
        )

    def create_module(self, spec) -> Optional[ModuleType]:
        if self.name in plugin_service.plugins:
            self.loaded = True
            return plugin_service.plugins[self.name].proxy()
        return super().create_module(spec)

    def exec_module(self, module: ModuleType, config: Optional[dict[str, str]] = None) -> None:
        is_sub = False
        if plugin := plugin_service.plugins.get(self.parent_plugin_id) if self.parent_plugin_id else None:
            plugin.subplugins.add(module.__name__)
            plugin_service._subplugined[module.__name__] = plugin.id
            is_sub = True

        if self.loaded:
            return

        if config is None:
            key = module.__name__
            if key.startswith("arclet.entari.builtins.") and f"::{key[23:]}" in EntariConfig.instance.plugin:
                key = f"::{key[23:]}"
            elif key.startswith("entari_plugin_") and f"{key[14:]}" in EntariConfig.instance.plugin:
                key = f"{key[14:]}"
            config = EntariConfig.instance.plugin.get(key, {}).copy()
            config["$path"] = key
            config.pop("$priority", None)
            if key in EntariConfig.instance.prelude_plugin:
                config["$static"] = True  # type: ignore
        # create plugin before executing
        plugin = Plugin(module.__name__, module, config=(config or {}).copy())
        # for `dataclasses` module
        sys.modules[module.__name__] = plugin.proxy()  # type: ignore
        setattr(module, "__plugin__", plugin)

        # enter plugin context
        token = _current_plugin.set(plugin)
        if not plugin.is_static:
            token1 = scope_ctx.set(plugin._scope)
        try:
            super().exec_module(module)
        except Exception:
            plugin.dispose()
            raise
        finally:
            # leave plugin context
            delattr(module, "__cached__")
            if not plugin.is_static:
                scope_ctx.reset(token1)  # type: ignore
            _current_plugin.reset(token)

        # get plugin metadata
        metadata: Optional[PluginMetadata] = getattr(module, "__plugin_metadata__", None)
        if metadata and not plugin.metadata:
            plugin._metadata = metadata
        if not is_sub:
            log.plugin.success(f"loaded plugin <blue>{self.name!r}</blue>")
        else:
            log.plugin.trace(f"loaded sub-plugin <r>{plugin.id!r}</r> of <y>{self.parent_plugin_id!r}</y>")
        return


class _NamespacePath(_bootstrap_external._NamespacePath):  # type: ignore
    def _get_parent_path(self):
        parent_module_name, path_attr_name = self._find_parent_path_names()
        if parent_module_name in plugin_service.plugins:
            return plugin_service.plugins[parent_module_name].module.__path__
        return getattr(sys.modules[parent_module_name], path_attr_name)


def _path_find_spec(fullname, path=None, target=None):
    """Try to find a spec for 'fullname' on sys.path or 'path'.

    The search is based on sys.path_hooks and sys.path_importer_cache.
    """
    if path is None:
        path = sys.path
    spec = PathFinder._get_spec(fullname, path, target)  # type: ignore
    if spec is None:
        return None
    elif spec.loader is None:
        namespace_path = spec.submodule_search_locations
        if namespace_path:
            # We found at least one namespace path.  Return a spec which
            # can create the namespace package.
            spec.origin = None
            spec.submodule_search_locations = _NamespacePath(fullname, namespace_path, PathFinder._get_spec)  # type: ignore
            return spec
        else:
            return None
    else:
        return spec


class _PluginFinder(MetaPathFinder):
    @classmethod
    def find_spec(
        cls,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[ModuleType] = None,
    ):
        module_spec = _path_find_spec(fullname, path, target)
        if not module_spec:
            return
        module_origin = module_spec.origin
        if not module_origin:
            return
        if isinstance(module_spec.loader, ExtensionFileLoader):
            return
        if plug := _current_plugin.get(None):
            if plug.module.__spec__ and plug.module.__spec__.origin == module_spec.origin:
                return plug.module.__spec__
            if module_spec.parent and module_spec.parent == plug.module.__name__:
                module_spec.loader = PluginLoader(fullname, module_origin, plug.id)
                return module_spec
            elif module_spec.name in _SUBMODULE_WAITLIST.get(plug.module.__name__, ()):
                module_spec.loader = PluginLoader(fullname, module_origin, plug.id)
                plugin_service.referents.setdefault(module_spec.name, set()).add(plug.id)
                # _SUBMODULE_WAITLIST[plug.module.__name__].remove(module_spec.name)
                return module_spec
            if (
                module_spec.name in _ENSURE_IS_PLUGIN
                or module_spec.name.startswith("arclet.entari.builtins.")
                or module_spec.name.startswith("entari_plugin")
            ):
                module_spec.loader = PluginLoader(fullname, module_origin)
                plugin_service.referents.setdefault(module_spec.name, set()).add(plug.id)
                return module_spec

        if module_spec.name in plugin_service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin)
            return module_spec
        if module_spec.name in _ENSURE_IS_PLUGIN:
            module_spec.loader = PluginLoader(fullname, module_origin)
            return module_spec
        if module_spec.name in plugin_service._subplugined:
            module_spec.loader = PluginLoader(fullname, module_origin, plugin_service._subplugined[module_spec.name])
            return module_spec
        if module_spec.parent and module_spec.parent in plugin_service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin, module_spec.parent)
            return module_spec
        if module_spec.name.rpartition(".")[0] in plugin_service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin, module_spec.name.rpartition(".")[0])
            return module_spec
        return


def find_spec(name, package=None):
    fullname = resolve_name(name, package) if name.startswith(".") else name
    parent_name = fullname.rpartition(".")[0]
    if parent_name:
        parts = parent_name.split(".")
        _current = parts[0]
        if _current in plugin_service.plugins:
            parent = plugin_service.plugins[_current].module
            enter_plugin = True
        else:
            parent = __import__(_current, fromlist=["__path__"])
            enter_plugin = False
        _current += "."
        for part in parts[1:]:
            _current += part
            if _current in plugin_service.plugins:
                parent = plugin_service.plugins[_current].module
                enter_plugin = True
                _current += "."
                continue
            if _current in _ENSURE_IS_PLUGIN:
                parent = import_plugin(_current)
                if parent:
                    enter_plugin = True
                else:
                    parent = __import__(_current, fromlist=["__path__"])
                _current += "."
                continue
            if enter_plugin and (parent := import_plugin(_current)):
                pass
            else:
                enter_plugin = False
                parent = __import__(_current, fromlist=["__path__"])
            _current += "."
        try:
            parent_path = parent.__path__
        except AttributeError as e:
            raise ModuleNotFoundError(
                f"__path__ attribute not found on {parent_name!r} " f"while trying to find {fullname!r}",
                name=fullname,
            ) from e
    else:
        parent_path = None
    if spec := _PluginFinder.find_spec(fullname, parent_path):
        return spec
    module_spec = _path_find_spec(fullname, parent_path, None)
    if not module_spec:
        return
    module_origin = module_spec.origin
    if not module_origin:
        return
    if isinstance(module_spec.loader, ExtensionFileLoader):
        return
    module_spec.loader = PluginLoader(fullname, module_origin)
    return module_spec


def import_plugin(name, package=None, config: Optional[dict] = None):
    spec = find_spec(name, package)
    if spec:
        mod = module_from_spec(spec)
        if spec.loader:
            if isinstance(spec.loader, PluginLoader):
                spec.loader.exec_module(mod, config=config)
                sys.modules.pop(mod.__name__)
                for _imported in _IMPORTING:
                    sys.modules.pop(_imported, None)
                _IMPORTING.clear()
            else:
                spec.loader.exec_module(mod)
        return mod
    return


sys.meta_path.insert(0, _PluginFinder())
