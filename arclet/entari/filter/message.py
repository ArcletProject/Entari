from typing import Optional

from arclet.letoderea import Interface, JudgeAuxiliary, Scope
from satori import Channel, ChannelType


class DirectMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type == ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/direct_message"


class PublicMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type != ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/public_message"


class ReplyMeJudger(JudgeAuxiliary):

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return interface.ctx.get("is_reply_me", False)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/judge_reply_me"


class NoticeMeJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return interface.ctx.get("is_notice_me", False)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/judge_notice_me"


class ToMeJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        is_reply_me = interface.ctx.get("is_reply_me", False)
        is_notice_me = interface.ctx.get("is_notice_me", False)
        return is_reply_me or is_notice_me

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/judge_to_me"
