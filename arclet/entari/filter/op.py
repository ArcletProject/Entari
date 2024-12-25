from typing import TYPE_CHECKING, Optional

from arclet.letoderea import BaseAuxiliary, Interface

if TYPE_CHECKING:
    from .common import Filter


class IntersectFilter(BaseAuxiliary):
    def __init__(self, left: "Filter", right: "Filter"):
        self.left = left
        self.right = right

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        return await self.left.on_prepare(interface) and await self.right.on_prepare(interface)

    @property
    def id(self) -> str:
        return "entari.filter/intersect"


class UnionFilter(BaseAuxiliary):
    def __init__(self, left: "Filter", right: "Filter"):
        self.left = left
        self.right = right

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        return await self.left.on_prepare(interface) or await self.right.on_prepare(interface)

    @property
    def id(self) -> str:
        return "entari.filter/union"


class ExcludeFilter(BaseAuxiliary):
    def __init__(self, left: "Filter", right: "Filter"):
        self.left = left
        self.right = right

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        return await self.left.on_prepare(interface) and not await self.right.on_prepare(interface)

    @property
    def id(self) -> str:
        return "entari.filter/exclude"
