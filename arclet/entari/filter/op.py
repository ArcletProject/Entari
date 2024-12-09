from typing import Optional

from arclet.letoderea import Interface, JudgeAuxiliary, Scope


class IntersectFilter(JudgeAuxiliary):
    def __init__(self, left: JudgeAuxiliary, right: JudgeAuxiliary, priority: int = 10):
        self.left = left
        self.right = right
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return await self.left(scope, interface) and await self.right(scope, interface)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/intersect"


class UnionFilter(JudgeAuxiliary):
    def __init__(self, left: JudgeAuxiliary, right: JudgeAuxiliary, priority: int = 10):
        self.left = left
        self.right = right
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return await self.left(scope, interface) or await self.right(scope, interface)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/union"


class ExcludeFilter(JudgeAuxiliary):
    def __init__(self, left: JudgeAuxiliary, right: JudgeAuxiliary, priority: int = 10):
        self.left = left
        self.right = right
        super().__init__(priority=priority)

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return await self.left(scope, interface) and not await self.right(scope, interface)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/exclude"
