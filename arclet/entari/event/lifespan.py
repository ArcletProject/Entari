from arclet.letoderea import make_event
from satori.client import Account
from satori.model import LoginStatus


@make_event(name="entari.event/startup")
class Startup:
    pass


@make_event(name="entari.event/ready")
class Ready:
    pass


@make_event(name="entari.event/cleanup")
class Cleanup:
    pass


@make_event(name="entari.event/account_update")
class AccountUpdate:
    account: Account
    status: LoginStatus
