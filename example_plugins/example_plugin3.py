from arclet.entari import (
    Session,
    MessageCreatedEvent,
    Plugin,
    plugin,
    # Entari,
)


def __plugin_apply__(plug: Plugin):
    @plug.dispatch(MessageCreatedEvent)
    async def _(session: Session):
        await session.send(repr(plugin.get_plugin()))


def foo():
    print("This is a function in example_plugin3.py")
