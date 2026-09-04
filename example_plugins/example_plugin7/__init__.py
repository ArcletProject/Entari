from arclet.entari import BasicConfModel, metadata, plugin_config, register_schema

from .config import Config
from . import listener

metadata(__file__, description="1", config=Config)
conf = plugin_config(Config)


class Foo(BasicConfModel):
    abc: int


class Bar(BasicConfModel):
    xyz: str


if conf.tools:
    register_schema(
        "properties.tools",
        {"type": "object", "description": "Tools configuration", "properties": {}},
        replace=True
    )
    for tool in conf.tools:
        if tool == "foo":
            register_schema(
                f"properties.tools.properties.{tool}",
                Foo
            )
        elif tool == "bar":
            register_schema(
                f"properties.tools.properties.{tool}",
                Bar
            )
