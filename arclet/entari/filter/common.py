from typing import Callable, Union
from typing_extensions import TypeAlias

from arclet.letoderea import STOP, Contexts, Depends, Propagator, propagate
from arclet.letoderea.typing import Result
from satori import Channel, ChannelType, Guild, User

from ..session import Session


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


class _Filter(Propagator):
    def __init__(self):
        self.step: dict[int, Callable] = {}
        self.ops = []

    def get_flow(self, entry: bool = False):
        if not self.step:
            flow = lambda: True

        else:
            steps = [slot[1] for slot in sorted(self.step.items(), key=lambda x: x[0])]

            @propagate(*steps, prepend=True)
            async def flow(ctx: Contexts):
                return ctx.get("$result", False)

        other = []
        for op, f_ in self.ops:
            if op == "and":
                other.append(lambda result, res=Depends(f_.get_flow()): Result(result and res))
            elif op == "or":
                other.append(lambda result, res=Depends(f_.get_flow()): Result(result or res))
            else:
                other.append(lambda result, res=Depends(f_.get_flow()): Result(result and not res))
        propagate(*other)(flow)
        if entry:
            propagate(lambda result: None if result else STOP)(flow)
        return flow

    def compose(self):
        yield self.get_flow(entry=True), True, 0


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
