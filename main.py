from satori import Image
from arclet.entari import ContextSession, Entari, WebsocketsInfo, EntariCommands, load_plugin

commands = EntariCommands()


@commands.on("echoimg {img}")
async def echoimg(img: Image, session: ContextSession):
    await session.send_message([img])


load_plugin("example_plugin")

app = Entari(
    WebsocketsInfo(
        port=12345,
        path="foo"
    )
)

app.run()
