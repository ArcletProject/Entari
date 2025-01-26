from arclet.letoderea import STOP
from satori import Channel, ChannelType


async def direct_message(channel: Channel):
    if channel.type != ChannelType.DIRECT:
        return STOP


async def public_message(channel: Channel):
    if channel.type == ChannelType.DIRECT:
        return STOP


async def reply_me(is_reply_me: bool = False):
    if not is_reply_me:
        return STOP


async def notice_me(is_notice_me: bool = False):
    if not is_notice_me:
        return STOP


async def to_me(is_reply_me: bool = False, is_notice_me: bool = False):
    if not is_reply_me and not is_notice_me:
        return STOP
