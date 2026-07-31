from arclet.letoderea import STOP, Propagator, propagate
from arclet.letoderea.utils import TCallable

from ..config import EntariConfig
from ..session import Session


class superusers(Propagator):

    async def check(self, session: Session | None = None):
        if not session:
            return STOP
        config = EntariConfig.instance.basic.superusers
        if session.account.platform not in config:
            return STOP
        if not session.event.user:
            return STOP
        if session.event.user.id not in config[session.account.platform]:
            return STOP

    def compose(self):
        yield self.check, True, 50

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class admins(Propagator):

    async def check(self, session: Session | None = None):
        if not session:
            return STOP
        if session.event.member and session.event.member.roles:
            for role in session.event.member.roles:
                if any(keyword in role.id.lower() for keyword in ("admin", "administrator", "owner")):
                    return
        config = EntariConfig.instance.basic.superusers
        if (
            session.account.platform in config
            and session.event.user
            and session.event.user.id in config[session.account.platform]
        ):
            return
        return STOP

    def compose(self):
        yield self.check, True, 50

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)
