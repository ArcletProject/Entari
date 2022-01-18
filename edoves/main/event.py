from arclet.letoderea.entities.event import StructuredEvent
from .medium import BaseMedium


class BasicEvent(StructuredEvent):
    medium: BaseMedium

    def get_params(self):
        return self.param_export(
            Edoves=self.medium.purveyor.metadata.protocol.edoves,
            ModuleProtocol=self.medium.purveyor.metadata.protocol.edoves.module_protocol,
            NetworkProtocl=self.medium.purveyor.metadata.protocol,
            **{self.medium.__class__.__name__: self.medium},
            **{k: v for k, v in self.medium.__dict__.items() if k in self.medium.__annotations__}
        )
