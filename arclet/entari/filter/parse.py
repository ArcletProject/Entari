import ast
import re
import operator
import os

from satori import Channel, ChannelType, Guild, User
import simpleeval

from arclet.entari.config.util import GetattrDict
from arclet.entari.session import Session

NAMES = {
    "channel": Channel(id="123", type=ChannelType.TEXT),
    "guild": Guild(id="321"),
    "user": User(id="789"),
    "platform": "satori",
    "self_id": "456",
    "direct": ChannelType.DIRECT,
    "private": ChannelType.DIRECT,
    "text": ChannelType.TEXT,
    "public": ChannelType.TEXT,
    "voice": ChannelType.VOICE,
    "category": ChannelType.CATEGORY,
    "env": GetattrDict(os.environ),
    "message": "abcdefg",
    "reply_me": True,
    "notice_me": False,
    "to_me": True,
}
base = simpleeval.EvalWithCompoundTypes()
base.operators[ast.Is] = operator.is_
base.operators[ast.IsNot] = operator.is_not
# 禁用乘法: a * b
base.operators.pop(ast.Mult, None)
# 禁用幂运算: a ** b
base.operators.pop(ast.Pow, None)
# 禁用整除: a // b
base.operators.pop(ast.FloorDiv, None)
# 禁用位运算
for op in (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift, ast.Invert):
    base.operators.pop(op, None)
base.functions["regex"] = lambda pattern, string: re.match(pattern, string)


def parse_filter(expr: str):
    s = simpleeval.EvalWithCompoundTypes(operators=base.operators, functions=base.functions)
    s.expr = expr
    s.names = NAMES

    try:
        parsed = s.parse(expr)
        s._eval(parsed)
    except (simpleeval.InvalidExpression, TypeError, ValueError, NameError, SyntaxError):
        raise RuntimeError(f"Invalid filter expression: {expr}") from None

    async def check(session: Session | None = None, is_reply_me: bool = False, is_notice_me: bool = False):
        if not session:
            return True

        s.names = {
            "channel": session.event.channel,
            "guild": session.event.guild,
            "user": session.event.user,
            "platform": session.account.platform,
            "self_id": session.account.self_id,
            "direct": ChannelType.DIRECT,
            "private": ChannelType.DIRECT,
            "text": ChannelType.TEXT,
            "public": ChannelType.TEXT,
            "voice": ChannelType.VOICE,
            "category": ChannelType.CATEGORY,
            "env": GetattrDict(os.environ),
            "message": session.event.message.content if session.event.message else None,
            "reply_me": is_reply_me,
            "notice_me": is_notice_me,
            "to_me": is_reply_me or is_notice_me,
        }
        return bool(s._eval(parsed))

    return check
