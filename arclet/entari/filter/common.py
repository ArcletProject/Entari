from collections.abc import Awaitable
from typing import Callable, Optional, Union
from typing_extensions import TypeAlias

from arclet.letoderea import STOP, Propagator
from tarina.tools import run_sync

from ..session import Session
from .message import direct_message, notice_me, public_message, reply_me, to_me


def user(*ids: str):
    def check_user(session: Session):
        return (session.user.id in ids) if ids else True

    return check_user


def channel(*ids: str):
    def check_channel(session: Session):
        return (session.channel.id in ids) if ids else True

    return check_channel


def guild(*ids: str):
    def check_guild(session: Session):
        return (session.guild.id in ids) if ids else True

    return check_guild


def account(*ids: str):
    def check_account(session: Session):
        return (session.account.self_id in ids) if ids else True

    return check_account


def platform(*ids: str):
    def check_platform(session: Session):
        return (session.account.platform in ids) if ids else True

    return check_platform


_keys = {
    "user": (user, 2),
    "guild": (guild, 3),
    "channel": (channel, 4),
    "self": (account, 1),
    "platform": (platform, 0),
    "direct": (lambda: direct_message, 5),
    "private": (lambda: direct_message, 5),
    "public": (lambda: public_message, 6),
}

_mess_keys = {
    "reply_me": (reply_me, 7),
    "notice_me": (notice_me, 8),
    "to_me": (to_me, 9),
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


class _Filter(Propagator):
    def __init__(
        self,
        steps: list[Callable[[Session], Awaitable[bool]]],
        mess: list[Callable[[bool, bool], bool]],
        ops: list[tuple[str, "_Filter"]],
    ):
        self.steps = steps
        self.mess = mess
        self.ops = ops

    async def check(self, session: Optional[Session] = None, is_reply_me: bool = False, is_notice_me: bool = False):
        res = True
        if session and self.steps:
            res = all([await step(session) for step in self.steps])
        if self.mess:
            res = res and all(mess(is_reply_me, is_notice_me) for mess in self.mess)
        for op, f_ in self.ops:
            if op == "and":
                res = res and (await f_.check(session, is_reply_me, is_notice_me)) is None  # type: ignore
            elif op == "or":
                res = res or (await f_.check(session, is_reply_me, is_notice_me)) is None  # type: ignore
            else:
                res = res and (await f_.check(session, is_reply_me, is_notice_me)) is STOP  # type: ignore
        return None if res else STOP

    def compose(self):
        yield self.check, True, 0


def parse(patterns: PATTERNS):
    step: dict[int, Callable[[Session], Awaitable[bool]]] = {}
    mess: dict[int, Callable[[bool, bool], bool]] = {}
    ops: list[tuple[str, _Filter]] = []

    for key, value in patterns.items():
        if key in _keys:
            step[_keys[key][1]] = run_sync(
                _keys[key][0](*map(str, value)) if isinstance(value, list) else _keys[key][0]()
            )
        elif key in _mess_keys:
            if key == "reply_me":
                mess[_mess_keys[key][1]] = lambda is_reply_me, is_notice_me: (
                    True if _mess_keys[key][0](is_reply_me) is None else False
                )
            elif key == "notice_me":
                mess[_mess_keys[key][1]] = lambda is_reply_me, is_notice_me: (
                    True if _mess_keys[key][0](is_notice_me) is None else False
                )
            else:
                mess[_mess_keys[key][1]] = lambda is_reply_me, is_notice_me: (
                    True if _mess_keys[key][0](is_reply_me, is_notice_me) is None else False
                )
        elif key in _op_keys:
            op = _op_keys[key]
            if not isinstance(value, dict):
                raise ValueError(f"Expect a dict for operator {key}")
            ops.append((op, parse(value)))
        else:
            raise ValueError(f"Unknown key: {key}")

    return _Filter(
        steps=[slot[1] for slot in sorted(step.items(), key=lambda x: x[0])],
        mess=[slot[1] for slot in sorted(mess.items(), key=lambda x: x[0])],
        ops=ops,
    )
