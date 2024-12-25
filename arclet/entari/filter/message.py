from typing import Optional

from arclet.letoderea import BaseAuxiliary, Interface
from satori import Channel, ChannelType


class DirectMessageJudger(BaseAuxiliary):
    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type == ChannelType.DIRECT

    @property
    def id(self) -> str:
        return "entari.filter/direct_message"


class PublicMessageJudger(BaseAuxiliary):
    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type != ChannelType.DIRECT

    @property
    def id(self) -> str:
        return "entari.filter/public_message"


class ReplyMeJudger(BaseAuxiliary):

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        return interface.ctx.get("is_reply_me", False)

    @property
    def id(self) -> str:
        return "entari.filter/judge_reply_me"


class NoticeMeJudger(BaseAuxiliary):
    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        return interface.ctx.get("is_notice_me", False)

    @property
    def id(self) -> str:
        return "entari.filter/judge_notice_me"

    @property
    def before(self) -> set[str]:
        return {"entari.filter/judge_reply_me"}


class ToMeJudger(BaseAuxiliary):
    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        is_reply_me = interface.ctx.get("is_reply_me", False)
        is_notice_me = interface.ctx.get("is_notice_me", False)
        return is_reply_me or is_notice_me

    @property
    def id(self) -> str:
        return "entari.filter/judge_to_me"

    @property
    def before(self) -> set[str]:
        return {"entari.filter/judge_reply_me", "entari.filter/judge_notice_me"}
