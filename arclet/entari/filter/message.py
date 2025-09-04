from satori import ChannelType

from ..session import Session


async def direct_message(sess: Session):
    return sess.channel.type == ChannelType.DIRECT


async def public_message(sess: Session):
    return sess.channel.type != ChannelType.DIRECT


async def reply_me(is_reply_me: bool = False):
    return is_reply_me


async def notice_me(is_notice_me: bool = False):
    return is_notice_me


async def to_me(is_reply_me: bool = False, is_notice_me: bool = False):
    return is_reply_me or is_notice_me
