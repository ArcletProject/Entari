from typing import Any

from arclet.entari.config import ConfigModelAction

try:
    from msgspec import Struct, convert, field, structs
    from msgspec.json import schema

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

        @classmethod
        def schema(cls, t: type[Struct]):  # type: ignore
            return schema(t)

except ImportError:
    Struct = None
    field = None


def __getattr__(name):
    if name == "Struct":
        if Struct is None:
            raise ImportError("Please install `msgspec` first. Install with `pip install arclet-entari[model]`")
        return Struct
    if name == "field":
        if field is None:
            raise ImportError("Please install `msgspec` first. Install with `pip install arclet-entari[model]`")
        return field
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Struct", "field"]
