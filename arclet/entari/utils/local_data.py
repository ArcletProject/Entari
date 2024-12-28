from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Optional
from typing_extensions import ParamSpec
from weakref import finalize

from nonestorage import user_cache_dir, user_data_dir

from ..event.config import ConfigReload
from ..plugin.model import RootlessPlugin

P = ParamSpec("P")


def _ensure_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    elif not path.is_dir():
        raise RuntimeError(f"{path} is not a directory")


def _auto_create_dir(func: Callable[P, Path]) -> Callable[P, Path]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Path:
        path = func(*args, **kwargs)
        _ensure_dir(path)
        return path

    return wrapper


class LocalData:
    def __init__(self):
        self.root: Optional[Path] = None
        self.app_name = "Entari"
        self._temp_dir = TemporaryDirectory()
        finalize(self, lambda obj: obj._temp_dir.cleanup(), self)

    def _get_base_cache_dir(self) -> Path:
        return user_cache_dir(self.app_name).resolve() if self.root is None else self.root

    def _get_base_data_dir(self) -> Path:
        return user_data_dir(self.app_name).resolve() if self.root is None else self.root

    @_auto_create_dir
    def get_cache_dir(self, name: Optional[str]) -> Path:
        dir_ = self._get_base_cache_dir()
        return (dir_ / name) if name else dir_

    def get_cache_file(self, name: Optional[str], filename: str) -> Path:
        return self.get_cache_dir(name) / filename

    @_auto_create_dir
    def get_data_dir(self, plugin_name: Optional[str]) -> Path:
        dir_ = self._get_base_data_dir()
        return (dir_ / plugin_name) if plugin_name else dir_

    def get_data_file(self, plugin_name: Optional[str], filename: str) -> Path:
        return self.get_data_dir(plugin_name) / filename

    @_auto_create_dir
    def get_temp_dir(self) -> Path:
        return Path(self._temp_dir.name) / self.app_name

    def get_temp_file(self, filename: str) -> Path:
        return self.get_temp_dir() / filename


local_data = LocalData()


@RootlessPlugin.apply("localdata")
def localdata_apply(plg: RootlessPlugin):
    conf = plg.config
    if "root" in conf:
        local_data.root = Path(conf["root"])
    if "app_name" in conf:
        local_data.app_name = conf["app_name"]
        local_data._temp_dir.cleanup()
        local_data._temp_dir = TemporaryDirectory()

    @plg.use(ConfigReload)
    def reload_config(event: ConfigReload):
        if event.scope != "plugin":
            return
        if event.key != ".localdata":
            return
        conf = event.value
        if "root" in conf:
            local_data.root = Path(conf["root"])
        if "app_name" in conf:
            local_data.app_name = conf["app_name"]
            local_data._temp_dir.cleanup()
            local_data._temp_dir = TemporaryDirectory()
