from typing import Any

from arclet.entari.config import config_validator_register
from arclet.entari.plugin import declare_static, metadata

declare_static()
metadata(
    "model",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="More Config Model support for entari",
)


try:
    from pydantic import BaseModel, TypeAdapter

    @config_validator_register(BaseModel)
    def _pydantic_validate(data: dict[str, Any], base: type):
        return TypeAdapter(base).validate_python(data)

except ImportError:
    BaseModel = None

try:
    from msgspec import Struct, convert

    @config_validator_register(Struct)
    def _msgspec_validate(data: dict[str, Any], base: type):
        return convert(data, base)

except ImportError:
    Struct = None


def __getattr__(name):
    if name == "BaseModel":
        if BaseModel is None:
            raise ImportError("Please install `pydantic` first. Install with `pip install arclet-entari[model]`")
        return BaseModel
    if name == "Struct":
        if Struct is None:
            raise ImportError("Please install `msgspec` first. Install with `pip install arclet-entari[model]`")
        return Struct
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BaseModel", "Struct"]
