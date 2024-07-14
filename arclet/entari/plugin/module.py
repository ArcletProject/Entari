from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder, SourceFileLoader
from importlib.util import module_from_spec, resolve_name
import sys
from types import ModuleType
from typing import Optional

from .model import Plugin, PluginMetadata, _current_plugin
from .service import service


class PluginLoader(SourceFileLoader):
    def __init__(self, fullname: str, path: str) -> None:
        self.loaded = False
        super().__init__(fullname, path)

    def create_module(self, spec) -> Optional[ModuleType]:
        if self.name in service.plugins:
            self.loaded = True
            return service.plugins[self.name].module
        return super().create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        if self.loaded:
            return

        # create plugin before executing
        plugin = Plugin(module.__name__, module)
        setattr(module, "__plugin__", plugin)

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
            plugin.metadata = metadata
        return


def find_spec(name, package=None):
    fullname = resolve_name(name, package) if name.startswith(".") else name
    parent_name = fullname.rpartition(".")[0]
    if parent_name:
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
        if module_spec.name in service.plugins:
            module_spec.loader = PluginLoader(fullname, module_origin)
            return module_spec
        return


sys.meta_path.insert(0, _PluginFinder())
