from typing import Any, TypeVar

from arclet.entari.config import config_validator_register
from arclet.entari.plugin import metadata, declare_static
from pydantic import BaseModel, TypeAdapter

declare_static()
metadata(
    "pydantic",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="Pydantic Config Model support for entari",
)


TB = TypeVar("TB", bound=BaseModel)


@config_validator_register(BaseModel)
def _pydantic_validate(data: dict[str, Any], base: type[TB]) -> TB:
    return TypeAdapter(base).validate_python(data)


__all__ = ["BaseModel"]
