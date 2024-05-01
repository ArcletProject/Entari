from typing import Optional

from arclet.letoderea import Contexts, JudgeAuxiliary, Scope
from satori import Channel, ChannelType


class DirectMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[bool]:
        if "channel" not in context:
            return False
        channel: Channel = context["channel"]
        return channel.type == ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


is_direct_message = DirectMessageJudger()


class PublicMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[bool]:
        if "channel" not in context:
            return False
        channel: Channel = context["channel"]
        return channel.type != ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


is_public_message = PublicMessageJudger()
