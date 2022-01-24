from arclet.letoderea.entities.event import StructuredEvent
from typing import TYPE_CHECKING
from .medium import BaseMedium

if TYPE_CHECKING:
    from .module import BaseModule


class BasicEvent(StructuredEvent):
    medium: BaseMedium
    module: "BaseModule"

    def get_params(self):
        return self.param_export(
            edoves=self.medium.purveyor.metadata.protocol.scene.edoves,
            module_protocol=self.medium.purveyor.metadata.protocol.scene.module_protocol,
            network_protocl=self.medium.purveyor.metadata.protocol,
            module=self.module,
            **{self.medium.__class__.__name__: self.medium},
            **{k: v for k, v in self.medium.__dict__.items()}
        )
