from pathlib import Path
from typing import Any

from arclet.entari.config.file import register_dumper, register_loader

try:
    from tomlkit import dumps, loads
except ImportError:
    dumps = None
    loads = None


@register_loader("toml")
def toml_loader(text: str) -> dict[str, Any]:
    """
    Load a TOML file and return its content as a dictionary.
    """
    if loads is None:
        raise RuntimeError("tomlkit is not installed. Please install with `arclet-entari[toml]`")
    return loads(text)


@register_dumper("toml")
def toml_dumper(save_path: Path, origin: dict[str, Any], indent: int = 4):
    """
    Dump a dictionary to a TOML file.
    """
    if dumps is None:
        raise RuntimeError("tomlkit is not installed. Please install with `arclet-entari[toml]`")
    with open(save_path, "w+", encoding="utf-8") as f:
        f.write(dumps(origin))
