from arclet.letoderea import STOP
from satori import ChannelType

from ..session import Session


async def direct_message(sess: Session):
    if sess.channel.type != ChannelType.DIRECT:
        return STOP


async def public_message(sess: Session):
    if sess.channel.type == ChannelType.DIRECT:
        return STOP


def reply_me(is_reply_me: bool = False):
    if not is_reply_me:
        return STOP


def notice_me(is_notice_me: bool = False):
    if not is_notice_me:
        return STOP


def to_me(is_reply_me: bool = False, is_notice_me: bool = False):
    if not is_reply_me and not is_notice_me:
        return STOP
