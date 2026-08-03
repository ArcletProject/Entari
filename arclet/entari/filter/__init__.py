import inspect
from collections.abc import Awaitable, Callable
from typing import Final, TypeAlias
from typing_extensions import ParamSpec

from arclet.letoderea import enter_if
from tarina import is_coroutinefunction

from ..session import Session
from . import common
from .limit import interval as interval
from .limit import semaphore as semaphore
from .message import endswith as endswith
from .message import startswith as startswith
from .permission import admins as admins
from .permission import superusers as superusers

_SessionFilter: TypeAlias = Callable[[Session], bool] | Callable[[Session], Awaitable[bool]]


P = ParamSpec("P")


def _check_wrapper(func: Callable[P, _SessionFilter]):
    def wrapper(*args: P.args, **kwargs: P.kwargs):
        return enter_if(func(*args, **kwargs))

    return wrapper


class _Filter:
    user = staticmethod(_check_wrapper(common.user))
    guild = staticmethod(_check_wrapper(common.guild))
    channel = staticmethod(_check_wrapper(common.channel))
    self_ = staticmethod(_check_wrapper(common.account))
    platform = staticmethod(_check_wrapper(common.platform))
    direct = enter_if(common.direct_message)
    private = enter_if(common.direct_message)
    direct_message = enter_if(common.direct_message)
    public = enter_if(common.public_message)
    public_message = enter_if(common.public_message)
    notice_me = enter_if(common.notice_me)
    reply_me = enter_if(common.reply_me)
    to_me = enter_if(common.to_me)

    def __call__(self, func: _SessionFilter):
        sig = inspect.signature(func)
        name = next(iter(sig.parameters.values())).name

        if not is_coroutinefunction(func):

            async def _(*args, _func=func, **kwargs):
                return _func(*args, **kwargs)

            func = _
        func.__signature__ = sig.replace(
            parameters=[
                param.replace(annotation=Session) if param.name == name else param for param in sig.parameters.values()
            ]
        )
        return enter_if(func)


filter_: Final[_Filter] = _Filter()
F = filter_
