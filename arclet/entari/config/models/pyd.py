from typing import Any

from arclet.entari.config import ConfigModelAction

try:
    from pydantic import BaseModel, Field, TypeAdapter, json_schema

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

        @classmethod
        def schema(cls, t: type[BaseModel]):  # type: ignore
            return json_schema.model_json_schema(t)

except ImportError:
    BaseModel = None
    Field = None


def __getattr__(name):
    if name == "BaseModel":
        if BaseModel is None:
            raise ImportError("Please install `pydantic` first. Install with `pip install arclet-entari[model]`")
        return BaseModel
    if name == "Field":
        if Field is None:
            raise ImportError("Please install `pydantic` first. Install with `pip install arclet-entari[model]`")
        return Field
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BaseModel", "Field"]
