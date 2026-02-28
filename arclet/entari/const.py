from __future__ import annotations

from typing import TYPE_CHECKING

from arclet.letoderea.typing import CtxItem

if TYPE_CHECKING:
    from arclet.alconna import Alconna
    import satori
    from satori.client import Account

    from .message import MessageChain, Reply
    from .session import Session

ITEM_ACCOUNT: CtxItem[Account] = CtxItem.make("$account")
ITEM_ORIGIN_EVENT: CtxItem[satori.Event] = CtxItem.make("$origin_event")
ITEM_MESSAGE_ORIGIN: CtxItem[satori.MessageObject] = CtxItem.make("$message_origin")
ITEM_MESSAGE_CONTENT: CtxItem[MessageChain] = CtxItem.make("$message_content")
ITEM_MESSAGE_REPLY: CtxItem[Reply] = CtxItem.make("$message_reply")
ITEM_SESSION: CtxItem[Session] = CtxItem.make("$session")
ITEM_ALCONNA: CtxItem[Alconna] = CtxItem.make("$alconna_command")

ITEM_OPERATOR: CtxItem[satori.User] = CtxItem.make("$operator")
ITEM_USER: CtxItem[satori.User] = CtxItem.make("$user")
ITEM_CHANNEL: CtxItem[satori.Channel] = CtxItem.make("$channel")
ITEM_GUILD: CtxItem[satori.Guild] = CtxItem.make("$guild")
ITEM_MEMBER: CtxItem[satori.Member] = CtxItem.make("$member")
ITEM_ROLE: CtxItem[satori.Role] = CtxItem.make("$role")
ITEM_EMOJI_OBJECT: CtxItem[satori.EmojiObject] = CtxItem.make("$emoji_object")
ITEM_LOGIN: CtxItem[satori.Login] = CtxItem.make("$login")
ITEM_FRIEND: CtxItem[satori.Friend] = CtxItem.make("$friend")
