from arclet.entari import (
    Channel,
    Entari,
    EntariCommands,
    MessageCreatedEvent,
    Plugin,
    Session,
    WebsocketsInfo,
)

command = EntariCommands()


@command.on("add {a} {b}")
async def add(a: int, b: int, channel: Channel, session: Session):
    await session.send_message(channel, f"{a + b =}")


plug = Plugin(MessageCreatedEvent)


@plug.on()
async def _(event: MessageCreatedEvent):
    print(event.content)


app = Entari()
app.apply(
    WebsocketsInfo(
        port=5500,
        token="9491ee65f2e5322d050021d4ceaca05d42c3ff2fc2a457fdffeb315619bf3f91",
    )
)

app.run()
