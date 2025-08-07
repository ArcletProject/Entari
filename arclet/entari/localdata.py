from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Optional
from typing_extensions import ParamSpec
from weakref import finalize

from nonestorage import user_cache_dir, user_data_dir

from .config import BasicConfModel, config_model_validate, model_field
from .event.config import ConfigReload
from .plugin import RootlessPlugin, metadata, plugin_config

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
        self.global_path: bool = False
        self.app_name = "entari"
        self.base_dir: Optional[str] = None
        self._temp_dir = TemporaryDirectory(prefix=f"{self.app_name}_")
        finalize(self, lambda obj: obj._temp_dir.cleanup(), self)

    def _get_base_cache_dir(self) -> Path:
        if self.global_path:
            return user_cache_dir(self.app_name.title()).resolve()
        name = self.base_dir or f".{self.app_name.lstrip('.')}"
        return Path.cwd() / name / "cache"

    def _get_base_data_dir(self) -> Path:
        if self.global_path:
            return user_data_dir(self.app_name.title()).resolve()
        name = self.base_dir or f".{self.app_name.lstrip('.')}"
        return Path.cwd() / name / "data"

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
        return Path(self._temp_dir.name)

    def get_temp_file(self, filename: str) -> Path:
        return self.get_temp_dir() / filename


local_data = LocalData()


class Config(BasicConfModel):
    use_global: bool = model_field(default=False, description="是否使用全局数据目录")
    app_name: str = model_field(default="entari", description="应用名称")
    base_dir: Optional[str] = model_field(
        default=None, description="基础目录，默认为空，表示使用 `app_name` 作为目录名，"
    )


@RootlessPlugin.apply("localdata", default=True)
def localdata_apply(plg: RootlessPlugin):
    metadata("LocalData", ["RF-Tar-Railt <rf_tar_railt@qq.com>"], config=Config)

    conf = plugin_config(Config)
    local_data.global_path = conf.use_global
    local_data.app_name = conf.app_name.lower()
    local_data._temp_dir.cleanup()
    local_data._temp_dir = TemporaryDirectory(prefix=f"{local_data.app_name}_")
    local_data.base_dir = conf.base_dir

    @plg.dispatch(ConfigReload)
    def reload_config(event: ConfigReload):
        if event.scope != "plugin":
            return
        if event.key != ".localdata":
            return
        conf1 = config_model_validate(Config, event.value)
        local_data.global_path = conf1.use_global
        local_data.app_name = conf1.app_name.lower()
        local_data._temp_dir.cleanup()
        local_data._temp_dir = TemporaryDirectory(prefix=f"{local_data.app_name}_")
        local_data.base_dir = conf1.base_dir
        return True
