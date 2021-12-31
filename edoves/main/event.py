from arclet.letoderea.entities.event import StructuredEvent
from .medium import BaseMedium


class BasicEvent(StructuredEvent):
    medium: BaseMedium

    def get_params(self):
        return self.param_export(
            Medium=self.medium
        )
