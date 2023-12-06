from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Optional
from . import Component

if TYPE_CHECKING:
    from ..interact import InteractiveObject
    from ..medium import BaseMedium


class BaseBehavior(Component, metaclass=ABCMeta):

    def __init__(self, io: "InteractiveObject"):
        super().__init__(io)
        self.activate()

    async def set_active(self, value: bool):
        super(BaseBehavior, self).set_active(value)
        if self.is_enable:
            await self.on_enable()
        else:
            await self.on_disable()

    async def handler_medium(
            self,
            medium: Optional["BaseMedium"] = None,
            medium_type: Optional["BaseMedium"] = None,
            **kwargs
    ):
        if not medium:
            await self.io.protocol.get_medium(medium_type, **kwargs)
        pass

    @abstractmethod
    def activate(self):
        """Behavior 初始化时调用"""

    async def start(self):
        """当主程序激活时调用"""
        pass

    async def update(self):
        """主程序会以固定时间间隔调用该方法"""
        pass

    async def quit(self):
        """当主程序关闭时调用"""

    async def on_enable(self):
        pass

    async def on_disable(self):
        pass
