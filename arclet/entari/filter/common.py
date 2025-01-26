from collections.abc import Awaitable
from inspect import Parameter, Signature
from typing import Callable, Union
from typing_extensions import TypeAlias

from arclet.letoderea import STOP, Contexts, Depends, Propagator, propagate
from arclet.letoderea.typing import Result, run_sync
from satori import Channel, ChannelType, Guild, User
from tarina import is_coroutinefunction

from ..session import Session

_SessionFilter: TypeAlias = Union[Callable[[Session], bool], Callable[[Session], Awaitable[bool]]]


def _user(*ids: str):
    async def check_user(user: User):
        return Result(user.id in ids if ids else True)

    return check_user


def _channel(*ids: str):
    async def check_channel(channel: Channel):
        return Result(channel.id in ids if ids else True)

    return check_channel


def _guild(*ids: str):
    async def check_guild(guild: Guild):
        return Result(guild.id in ids if ids else True)

    return check_guild


def _account(*ids: str):
    async def check_account(session: Session):
        return Result(session.account.self_id in ids)

    return check_account


def _platform(*ids: str):
    async def check_platform(session: Session):
        return Result(session.account.platform in ids)

    return check_platform


_keys = {
    "user": (_user, 2),
    "guild": (_guild, 3),
    "channel": (_channel, 4),
    "self": (_account, 1),
    "platform": (_platform, 0),
}

_mess_keys = {
    "direct": (lambda channel: Result(channel.type == ChannelType.DIRECT), 5),
    "private": (lambda channel: Result(channel.type == ChannelType.DIRECT), 5),
    "public": (lambda channel: Result(channel.type != ChannelType.DIRECT), 6),
    "reply_me": (lambda is_reply_me=False: Result(is_reply_me), 7),
    "notice_me": (lambda is_notice_me=False: Result(is_notice_me), 8),
    "to_me": (lambda is_reply_me=False, is_notice_me=False: Result(is_reply_me or is_notice_me), 9),
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


class _Filter(Propagator):
    def __init__(self):
        self.step: dict[int, Callable] = {}
        self.ops = []

    def get_flow(self):
        if not self.step:
            return Depends(lambda: None)

        steps = [slot[1] for slot in sorted(self.step.items(), key=lambda x: x[0])]

        @propagate(*steps, prepend=True)
        async def flow(ctx: Contexts):
            if ctx.get("$result", False):
                return
            return STOP

        return Depends(flow)

    def generate(self):
        async def check(**kwargs):
            res = kwargs["res"]
            for (op, _), res1 in zip(self.ops, list(kwargs.values())[1:]):
                if op == "and" and (res is None and res1 is None):
                    continue
                if op == "or" and (res is None or res1 is None):
                    res = None
                    continue
                if op == "not" and (res is None and res1 is STOP):
                    continue
                res = STOP
            return res

        param = [Parameter("res", Parameter.POSITIONAL_OR_KEYWORD, default=self.get_flow())]
        for index, slot in enumerate(self.ops):
            param.append(
                Parameter(f"res_{index+1}", Parameter.POSITIONAL_OR_KEYWORD, default=Depends(slot[1].generate()))
            )
        check.__signature__ = Signature(param)
        return check

    def compose(self):
        yield self.generate(), True, 0


def parse(patterns: PATTERNS):
    f = _Filter()

    for key, value in patterns.items():
        if key in _keys:
            f.step[_keys[key][1]] = _keys[key][0](*value)
        elif key in _mess_keys:
            if value is True:
                f.step[_mess_keys[key][1]] = _mess_keys[key][0]
        elif key in _op_keys:
            op = _op_keys[key]
            if not isinstance(value, dict):
                raise ValueError(f"Expect a dict for operator {key}")
            f.ops.append((op, parse(value)))
        else:
            raise ValueError(f"Unknown key: {key}")

    return f
