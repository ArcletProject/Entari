from typing import Any

from arclet.entari.config import ConfigModelAction
from arclet.entari.plugin import declare_static, metadata

declare_static()
metadata(
    "model",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="More Config Model support for entari",
)


try:
    from pydantic import BaseModel, TypeAdapter

    class PydanticConfigAction(ConfigModelAction[BaseModel]):
        """Pydantic Config Model Action"""

        @classmethod
        def load(cls, data: dict[str, Any], t: type):
            return TypeAdapter(t).validate_python(data)

        @classmethod
        def dump(cls, obj):
            return obj.model_dump()

        @classmethod
        def keys(cls, obj) -> list[str]:
            return list(obj.model_fields.keys())

except ImportError:
    BaseModel = None

try:
    from msgspec import Struct, convert, structs

    class MsgspecConfigAction(ConfigModelAction[Struct]):
        """Msgspec Config Model Action"""

        @classmethod
        def load(cls, data: dict[str, Any], t: type):
            return convert(data, t)

        @classmethod
        def dump(cls, obj):
            return structs.asdict(obj)

        @classmethod
        def keys(cls, obj) -> list[str]:
            return [field.name for field in structs.fields(obj)]

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
