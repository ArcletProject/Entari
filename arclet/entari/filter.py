from typing import Optional

from arclet.letoderea import Interface, JudgeAuxiliary, Scope
from satori import Channel, ChannelType


class DirectMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type == ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


is_direct_message = DirectMessageJudger()


class PublicMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type != ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


is_public_message = PublicMessageJudger()
