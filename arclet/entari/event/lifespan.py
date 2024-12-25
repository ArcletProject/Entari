from dataclasses import dataclass

from arclet.letoderea import make_event
from satori.client import Account
from satori.model import LoginStatus


@dataclass
@make_event(name="entari.event/startup")
class Startup:
    pass


@dataclass
@make_event(name="entari.event/ready")
class Ready:
    pass


@dataclass
@make_event(name="entari.event/cleanup")
class Cleanup:
    pass


@dataclass
@make_event(name="entari.event/account_update")
class AccountUpdate:
    account: Account
    status: LoginStatus
