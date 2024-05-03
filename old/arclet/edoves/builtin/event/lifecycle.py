from arclet.edoves.main.context import edoves_instance
from arclet.edoves.main.event import EdovesBasicEvent


class LifeCycle(EdovesBasicEvent):

    def get_params(self):
        return self.param_export(
            edoves=edoves_instance.get(),
        )


class StartRunning(LifeCycle):
    pass


class StopRunning(LifeCycle):
    pass
