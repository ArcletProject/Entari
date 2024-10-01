import ast
from collections.abc import Sequence
from importlib import _bootstrap  # type: ignore
from importlib import import_module
from importlib.abc import MetaPathFinder
from importlib.machinery import ExtensionFileLoader, PathFinder, SourceFileLoader
from importlib.util import module_from_spec, resolve_name
import sys
from types import ModuleType
from typing import Optional

from .model import Plugin, PluginMetadata, _current_plugin
from .service import plugin_service

_SUBMODULE_WAITLIST: dict[str, set[str]] = {}
_ENSURE_IS_PLUGIN: set[str] = set()


def package(*names: str):
    """手动指定特定模块作为插件的子模块"""
    if not (plugin := _current_plugin.get(None)):
        raise LookupError("no plugin context found")
    _SUBMODULE_WAITLIST.setdefault(plugin.module.__name__, set()).update(names)


def requires(*names: str):
    """手动指定哪些模块是插件"""
    _ENSURE_IS_PLUGIN.update(names)


def __entari_import__(name: str, plugin_name: str, ensure_plugin: bool = False):
    if name in plugin_service.plugins:
        plug = plugin_service.plugins[name]
        if plugin_name != plug.id:
            plugin_service._referents[plug.id].add(plugin_name)
        return plug.proxy()
    if name in _SUBMODULE_WAITLIST.get(plugin_name, ()):
        mod = import_plugin(name)
        if mod:
            if plugin_name != mod.__plugin__.id:
                plugin_service._referents[mod.__plugin__.id].add(plugin_name)
            return mod.__plugin__.subproxy(name)
        return __import__(name, fromlist=["__path__"])
    if name in _ENSURE_IS_PLUGIN:
        mod = import_plugin(name)
        if mod:
            if plugin_name != mod.__plugin__.id:
                plugin_service._referents[mod.__plugin__.id].add(plugin_name)
            return mod.__plugin__.proxy()
        return __import__(name, fromlist=["__path__"])
    if ensure_plugin:
        module = import_plugin(name, plugin_name)
        if not module:
            raise ModuleNotFoundError(f"module {name!r} not found")
        if hasattr(module, "__plugin__"):
            if plugin_name != module.__plugin__.id:
                plugin_service._referents[module.__plugin__.id].add(plugin_name)
            return module.__plugin__.subproxy(f"{plugin_name}{name}")
        return module
    if not name.startswith("."):
        return __import__(name, fromlist=["__path__"])
    return import_module(f".{name}", plugin_name)


def getattr_or_import(module, name):
    try:
        return getattr(module, name)
    except AttributeError:
        return __entari_import__(f".{name}", module.__name__, True)


class PluginLoader(SourceFileLoader):
    def __init__(self, fullname: str, path: str, parent_plugin_id: Optional[str] = None) -> None:
        self.loaded = False
        self.parent_plugin_id = parent_plugin_id
        super().__init__(fullname, path)

    def source_to_code(self, data, path, *, _optimize=-1):  # type: ignore
        """Return the code object compiled from source.

        The 'data' argument can be any object type that compile() supports.
        """
        try:
            nodes = ast.parse(data, type_comments=True)
        except SyntaxError:
            return _bootstrap._call_with_frames_removed(
                compile, data, path, "exec", dont_inherit=True, optimize=_optimize
            )
        bodys = []
        for body in nodes.body:
            if isinstance(body, ast.ImportFrom):
                if body.level == 0:
                    if body.module == "__future__":
                        print(1)
                        bodys.append(body)
                        continue
                    if len(body.names) == 1 and body.names[0].name == "*":
                        new = ast.parse(
                            f"__mod = __entari_import__({body.module!r}, {self.name!r});"
                            f"__mod_all = getattr(__mod, '__all__', dir(__mod));"
                            "globals().update("
                            "{name: getattr(__mod, name) for name in __mod_all if not name.startswith('__')}"
                            ");"
                            "del __mod, __mod_all"
                        )
                    else:
                        new = ast.parse(
                            f"__mod = __entari_import__({body.module!r}, {self.name!r});"
                            + ";".join(
                                f"{alias.asname or alias.name} = __getattr_or_import__(__mod, {alias.name!r})"
                                for alias in body.names
                            )
                            + ";del __mod"
                        )
                    for node in ast.walk(new):
                        node.lineno = body.lineno  # type: ignore
                        node.end_lineno = body.end_lineno  # type: ignore
                    bodys.extend(new.body)
                elif body.module is None:
                    relative = "." * body.level
                    if len(body.names) == 1 and body.names[0].name == "*":
                        bodys.append(body)
                    else:
                        new = ast.parse(
                            ";".join(
                                f"{alias.asname or alias.name}="
                                f"__entari_import__('{relative}{alias.name}', {self.name!r}, {body.level == 1})"
                                for alias in body.names
                            )
                        )
                        for node in ast.walk(new):
                            node.lineno = body.lineno  # type: ignore
                            node.end_lineno = body.end_lineno  # type: ignore
                        bodys.extend(new.body)
                else:
                    relative = "." * body.level
                    if len(body.names) == 1 and body.names[0].name == "*":
                        new = ast.parse(
                            f"__mod = __entari_import__('{relative}{body.module}', {self.name!r}, {body.level == 1});"
                            f"__mod_all = getattr(__mod, '__all__', dir(__mod));"
                            "globals().update("
                            "{name: getattr(__mod, name) for name in __mod_all if not name.startswith('__')}"
                            ");"
                            "del __mod, __mod_all"
                        )
                    else:
                        new = ast.parse(
                            f"__mod = __entari_import__('{relative}{body.module}', {self.name!r}, {body.level == 1});"
                            + ";".join(
                                f"{alias.asname or alias.name} = __getattr_or_import__(__mod, {alias.name!r})"
                                for alias in body.names
                            )
                            + ";del __mod"
                        )
                    for node in ast.walk(new):
                        node.lineno = body.lineno  # type: ignore
                        node.end_lineno = body.end_lineno  # type: ignore
                    bodys.extend(new.body)
            elif isinstance(body, ast.Import):
                aliases = [alias.asname or alias.name for alias in body.names]
                new = ast.parse(
                    ",".join(aliases)
                    + "="
                    + ",".join(f"__entari_import__({alias.name!r}, {self.name!r})" for alias in body.names)
                )
                for node in ast.walk(new):
                    node.lineno = body.lineno  # type: ignore
                    node.end_lineno = body.end_lineno  # type: ignore
                bodys.append(new.body[0])
            else:
                bodys.append(body)
        nodes.body = bodys
        return _bootstrap._call_with_frames_removed(compile, nodes, path, "exec", dont_inherit=True, optimize=_optimize)

    def create_module(self, spec) -> Optional[ModuleType]:
        if self.name in plugin_service.plugins:
            self.loaded = True
            return plugin_service.plugins[self.name].proxy()
        return super().create_module(spec)

    def exec_module(self, module: ModuleType, config: Optional[dict[str, str]] = None) -> None:
        if plugin := plugin_service.plugins.get(self.parent_plugin_id) if self.parent_plugin_id else None:
            plugin.subplugins.add(module.__name__)
            plugin_service._subplugined[module.__name__] = plugin.id

        if self.loaded:
            return

        # create plugin before executing
        plugin = Plugin(module.__name__, module, config=config or {})
        setattr(module, "__plugin__", plugin)
        setattr(module, "__entari_import__", __entari_import__)
        setattr(module, "__getattr_or_import__", getattr_or_import)

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


class _PluginFinder(MetaPathFinder):
    @classmethod
    def find_spec(
        cls,
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
                # _SUBMODULE_WAITLIST[plug.module.__name__].remove(module_spec.name)
                return module_spec

        if module_spec.name in plugin_service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin)
            return module_spec
        if module_spec.name in plugin_service._subplugined:
            module_spec.loader = PluginLoader(fullname, module_origin, plugin_service._subplugined[module_spec.name])
            return module_spec
        if module_spec.parent and module_spec.parent in plugin_service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin, module_spec.parent)
            return module_spec
        return


def find_spec(name, package=None):
    fullname = resolve_name(name, package) if name.startswith(".") else name
    parent_name = fullname.rpartition(".")[0]
    if parent_name:
        if parent_name in plugin_service.plugins:
            parent = plugin_service.plugins[parent_name].module

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
    if spec := _PluginFinder.find_spec(fullname, parent_path):
        return spec
    module_spec = PathFinder.find_spec(fullname, parent_path, None)
    if not module_spec:
        return
    module_origin = module_spec.origin
    if not module_origin:
        return
    module_spec.loader = PluginLoader(fullname, module_origin)
    return module_spec


def import_plugin(name, package=None, config: Optional[dict[str, str]] = None):
    spec = find_spec(name, package)
    if spec:
        mod = module_from_spec(spec)
        if spec.loader:
            if isinstance(spec.loader, PluginLoader):
                spec.loader.exec_module(mod, config=config)
            else:
                spec.loader.exec_module(mod)
        return mod
    return


sys.meta_path.insert(0, _PluginFinder())
