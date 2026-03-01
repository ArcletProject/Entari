import ast
import operator
import os
import re

from satori import Channel, ChannelType, EventType, Guild, Member, Role, User
import simpleeval

from ..config import EntariConfig
from ..config.util import GetattrDict
from ..session import Session

NAMES = {
    "type": EventType.MESSAGE_CREATED,
    "channel": Channel(id="123", type=ChannelType.TEXT),
    "guild": Guild(id="321"),
    "user": User(id="789"),
    "member": Member(User(id="789")),
    "platform": "satori",
    "self_id": "456",
    "direct": ChannelType.DIRECT,
    "private": ChannelType.DIRECT,
    "text": ChannelType.TEXT,
    "public": ChannelType.TEXT,
    "voice": ChannelType.VOICE,
    "category": ChannelType.CATEGORY,
    "role": Role(id="member"),
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

_op_translate = {
    " exists": " is not None",
    " eq ": " == ",
    " ne ": " != ",
    " neq ": " != ",
    " gt ": " > ",
    " lt ": " < ",
    " ge ": " >= ",
    " gte ": " >= ",
    " le ": " <= ",
    " lte ": " <= ",
    " nin ": " not in ",
}


def regex_batch_replace(text, replace_dict):
    pattern = re.compile("|".join(map(re.escape, replace_dict.keys())))
    return pattern.sub(lambda m: replace_dict[m.group()], text)


def evaluate_disable(expr: str):
    expr = regex_batch_replace(expr, _op_translate)
    s = simpleeval.EvalWithCompoundTypes(operators=base.operators, functions=base.functions)
    s.names = {"env": GetattrDict(EntariConfig.instance.env_vars), "config": GetattrDict(EntariConfig.instance.data)}

    try:
        return bool(s.eval(expr))
    except (simpleeval.InvalidExpression, TypeError, ValueError, NameError, SyntaxError):
        raise RuntimeError(f"Invalid disable expression: {expr}") from None


def parse_filter(expr: str):
    expr = regex_batch_replace(expr, _op_translate)
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
            "type": session.event.type,
            "channel": session.event.channel,
            "guild": session.event.guild,
            "user": session.event.user,
            "member": session.event.member,
            "platform": session.account.platform,
            "self_id": session.account.self_id,
            "direct": ChannelType.DIRECT,
            "private": ChannelType.DIRECT,
            "text": ChannelType.TEXT,
            "public": ChannelType.TEXT,
            "voice": ChannelType.VOICE,
            "category": ChannelType.CATEGORY,
            "role": session.event.role,
            "env": GetattrDict(EntariConfig.instance.env_vars),
            "message": session.event.message.content if session.event.message else None,
            "reply_me": is_reply_me,
            "notice_me": is_notice_me,
            "to_me": is_reply_me or is_notice_me,
        }
        return bool(s._eval(parsed))

    return check
