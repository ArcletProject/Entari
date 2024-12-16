import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Callable, Literal, Optional
from typing_extensions import ParamSpec
from weakref import finalize

from ..event.config import ConfigReload
from ..plugin.model import RootlessPlugin

WINDOWS = sys.platform.startswith("win") or (sys.platform == "cli" and os.name == "nt")


def user_cache_dir(appname: str) -> Path:
    r"""
    Return full path to the user-specific cache dir for this application.
        "appname" is the name of application.
    Typical user cache directories are:
        macOS:      ~/Library/Caches/<AppName>
        Unix:       ~/.cache/<AppName> (XDG default)
        Windows:    C:\Users\<username>\AppData\Local\<AppName>\Cache
    On Windows the only suggestion in the MSDN docs is that local settings go
    in the `CSIDL_LOCAL_APPDATA` directory. This is identical to the
    non-roaming app data dir (the default returned by `user_data_dir`). Apps
    typically put cache data somewhere *under* the given dir here. Some
    examples:
        ...\Mozilla\Firefox\Profiles\<ProfileName>\Cache
        ...\Acme\SuperApp\Cache\1.0
    OPINION: This function appends "Cache" to the `CSIDL_LOCAL_APPDATA` value.
    """
    if WINDOWS:
        return _get_win_folder("CSIDL_LOCAL_APPDATA") / appname / "Cache"
    elif sys.platform == "darwin":
        return Path("~/Library/Caches").expanduser() / appname
    else:
        return Path(os.getenv("XDG_CACHE_HOME", "~/.cache")).expanduser() / appname


def user_data_dir(appname: str, roaming: bool = False) -> Path:
    r"""
    Return full path to the user-specific data dir for this application.
        "appname" is the name of application.
            If None, just the system directory is returned.
        "roaming" (boolean, default False) can be set True to use the Windows
            roaming appdata directory. That means that for users on a Windows
            network setup for roaming profiles, this user data will be
            sync'd on login. See
            <http://technet.microsoft.com/en-us/library/cc766489(WS.10).aspx>
            for a discussion of issues.
    Typical user data directories are:
        macOS:                  ~/Library/Application Support/<AppName>
        Unix:                   ~/.local/share/<AppName>    # or in
                                $XDG_DATA_HOME, if defined
        Win XP (not roaming):   C:\Documents and Settings\<username>\ ...
                                ...Application Data\<AppName>
        Win XP (roaming):       C:\Documents and Settings\<username>\Local ...
                                ...Settings\Application Data\<AppName>
        Win 7  (not roaming):   C:\Users\<username>\AppData\Local\<AppName>
        Win 7  (roaming):       C:\Users\<username>\AppData\Roaming\<AppName>
    For Unix, we follow the XDG spec and support $XDG_DATA_HOME.
    That means, by default "~/.local/share/<AppName>".
    """
    if WINDOWS:
        const = "CSIDL_APPDATA" if roaming else "CSIDL_LOCAL_APPDATA"
        return Path(_get_win_folder(const)) / appname
    elif sys.platform == "darwin":
        return Path("~/Library/Application Support/").expanduser() / appname
    else:
        return Path(os.getenv("XDG_DATA_HOME", "~/.local/share")).expanduser() / appname


# -- Windows support functions --
def _get_win_folder_from_registry(
    csidl_name: Literal["CSIDL_APPDATA", "CSIDL_COMMON_APPDATA", "CSIDL_LOCAL_APPDATA"]
) -> Path:
    """
    This is a fallback technique at best. I'm not sure if using the
    registry for this guarantees us the correct answer for all CSIDL_*
    names.
    """
    import winreg

    shell_folder_name = {
        "CSIDL_APPDATA": "AppData",
        "CSIDL_COMMON_APPDATA": "Common AppData",
        "CSIDL_LOCAL_APPDATA": "Local AppData",
    }[csidl_name]

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
    )
    directory, _type = winreg.QueryValueEx(key, shell_folder_name)
    return Path(directory)


def _get_win_folder_with_ctypes(
    csidl_name: Literal["CSIDL_APPDATA", "CSIDL_COMMON_APPDATA", "CSIDL_LOCAL_APPDATA"]
) -> Path:
    csidl_const = {
        "CSIDL_APPDATA": 26,
        "CSIDL_COMMON_APPDATA": 35,
        "CSIDL_LOCAL_APPDATA": 28,
    }[csidl_name]

    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl_const, None, 0, buf)

    # Downgrade to short path name if have highbit chars. See
    # <http://bugs.activestate.com/show_bug.cgi?id=85099>.
    has_high_char = any(ord(c) > 255 for c in buf)
    if has_high_char:
        buf2 = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(buf.value, buf2, 1024):
            buf = buf2

    return Path(buf.value)


if WINDOWS:
    try:
        import ctypes

        _get_win_folder = _get_win_folder_with_ctypes
    except ImportError:
        _get_win_folder = _get_win_folder_from_registry


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
        finalize(local_data, lambda obj: obj._temp_dir.cleanup(), self)

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
