from ...main.event import EdovesBasicEvent
from ...main.context import edoves_instance


class LifeCycle(EdovesBasicEvent):

    def get_params(self):
        return self.param_export(
            edoves=edoves_instance.get(),
        )


class StartRunning(LifeCycle):
    pass


class StopRunning(LifeCycle):
    pass
