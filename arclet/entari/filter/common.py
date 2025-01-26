from collections.abc import Awaitable
from typing import Callable, Union
from typing_extensions import TypeAlias

from arclet.letoderea import STOP
from arclet.letoderea.handler import run_handler
from arclet.letoderea.typing import run_sync
from tarina import is_coroutinefunction

from ..event.base import MessageEvent
from ..session import Session
from .message import direct_message, notice_me, public_message, reply_me, to_me

_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]
_sess_keys = {
    "user",
    "guild",
    "channel",
    "self",
    "platform",
}

_message_keys = {
    "direct": direct_message,
    "private": direct_message,
    "public": public_message,
    "reply_me": reply_me,
    "notice_me": notice_me,
    "to_me": to_me,
}

_op_keys = {
    "$and": "and",
    "$or": "or",
    "$not": "not",
    "$intersect": "and",
    "$union": "or",
    "$exclude": "not",
}

PATTERNS: TypeAlias = dict[str, Union[list[str], bool, "PATTERNS"]]


def filter_(func: _SessionFilter):
    if is_coroutinefunction(func):
        _func = func
    else:
        _func = run_sync(func)

    async def _(session: Session):
        if not await _func(session):
            return STOP

    return _


def parse(patterns: PATTERNS):
    step: list[Callable[[Session], bool]] = []
    other = []
    ops = []
    for key, value in patterns.items():
        if key in _sess_keys:
            step.append(lambda session: getattr(session, key) in value)
        elif key in _message_keys:
            step.append(lambda session: isinstance(session.event, MessageEvent))
            other.append(_message_keys[key])
        elif key in _op_keys:
            op = _op_keys[key]
            if not isinstance(value, dict):
                raise ValueError(f"Expect a dict for operator {key}")
            ops.append((op, parse(value)))
        else:
            raise ValueError(f"Unknown key: {key}")

    async def f(session: Session):
        for i in step:
            if not i(session):
                return STOP
        for i in other:
            if not await run_handler(i, session.event):
                return STOP

    if not ops:
        return f

    async def _(session: Session):
        res = await f(session)

        for op, f_ in ops:
            res1 = await f_(session)
            if op == "and" and (res is None and res1 is None):
                return
            if op == "or" and (res is None or res1 is None):
                return
            if op == "not" and (res is None and res1 is STOP):
                return
            return STOP

    return _
