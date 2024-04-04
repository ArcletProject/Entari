from satori import Image
from arclet.entari import ContextSession, Entari, EntariCommands, MessageCreatedEvent, Plugin, WebsocketsInfo

command = EntariCommands()


@command.on("echoimg {img}")
async def echoimg(img: Image, session: ContextSession):
    await session.send_message([img])


@command.on("add {a} {b}")
async def add(a: int, b: int, session: ContextSession):
    await session.send_message(f"{a + b =}")


plug = Plugin(MessageCreatedEvent)


@plug.on()
async def _(event: MessageCreatedEvent):
    print(event.content)


app = Entari()
app.apply(
    WebsocketsInfo(
        port=7777,
        token="fa1ccfd6a9fcac523f3af2f67575e54230b1aef5df69a6886a3bae140e39a13b",
    )
)

app.run()
