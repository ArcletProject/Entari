from ...main.event import EdovesBasicEvent
from ...main.context import ctx_edoves


class LifeCycle(EdovesBasicEvent):

    def get_params(self):
        return self.param_export(
            edoves=ctx_edoves.get(),
        )


class StartRunning(LifeCycle):
    pass


class StopRunning(LifeCycle):
    pass
