from typing import Type, Generic
from ..builtin.medium import JsonMedium
from .typings import TNProtocol
from .module import BaseModule
from ..utilles import ModuleStatus


class BaseDockServer(Generic[TNProtocol], BaseModule):
    protocol: TNProtocol
    medium_type: Type[JsonMedium]

    def __init__(self, protocol: TNProtocol):
        super().__init__(protocol)
        self.state = ModuleStatus.MEDIUM_WAIT

    def connect(self):
        self.protocol.config.get("host")

    def catch(self):
        medium = self.protocol.medium
        if medium.get("start"):
            return True
