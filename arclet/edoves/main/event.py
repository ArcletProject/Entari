from arclet.letoderea.entities.event import StructuredEvent
from .medium import BaseMedium
from .context import ctx_module, edoves_instance, ctx_monomer


class EdovesBasicEvent(StructuredEvent):
    medium: BaseMedium

    def medium_vars(self):
        return {k: v for k, v in self.medium.__dict__.items()}

    def get_params(self):
        return self.param_export(
            edoves=edoves_instance.get(),
            sender=ctx_monomer.get(),
            module=ctx_module.get(),
            protocol=self.medium.purveyor.metadata.protocol,
            medium=self.medium,
            **self.medium_vars()
        )

    def __repr__(self) -> str:
        return (
            f"Event:{self.__class__.__name__}; "
            f"{' '.join([f'{k}={v.__repr__()}' for k, v in self.medium_vars().items()])}>"
        )
