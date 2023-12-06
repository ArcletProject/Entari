from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from arclet.letoderea import BaseEvent, Publisher, system_ctx


@dataclass
class PluginMeta:
    author: list[str] = field(default_factory=list)
    name: str | None = None
    version: str | None = None
    license: str | None = None
    urls: dict[str, str] | None = None
    description: str | None = None
    icon: str | None = None
    classifier: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    standards: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    config_endpoints: list[str] = field(default_factory=list)
    component_endpoints: list[str] = field(default_factory=list)


plugins = {}


class Plugin(Publisher):
    def __init__(
        self,
        *events: type[BaseEvent],
        meta: PluginMeta | None = None,
        predicate: Callable[[BaseEvent], bool] | None = None,
    ):
        meta = meta or PluginMeta()
        super().__init__(meta.name or self.__module__, *events, predicate=predicate)
        self.meta = meta
        if es := system_ctx.get():
            es.register(self)
        else:
            plugins[self.id] = self

    on = Publisher.register
    handle = Publisher.register
