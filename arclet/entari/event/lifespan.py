from dataclasses import dataclass

from arclet.letoderea import es
from satori.client import Account
from satori.model import LoginStatus

from .base import BasedEvent


@dataclass
class Startup(BasedEvent):
    pass

    __publisher__ = "entari.event/startup"


@dataclass
class Ready(BasedEvent):
    pass

    __publisher__ = "entari.event/ready"


@dataclass
class Cleanup(BasedEvent):
    pass

    __publisher__ = "entari.event/cleanup"


@dataclass
class AccountUpdate(BasedEvent):
    account: Account
    status: LoginStatus

    __publisher__ = "entari.event/account_update"


es.define("entari.event/startup", Startup)
es.define("entari.event/ready", Ready)
es.define("entari.event/cleanup", Cleanup)
es.define("entari.event/account_update", AccountUpdate)
