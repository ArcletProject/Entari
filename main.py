from satori import Image
from arclet.entari import ContextSession, Entari, WebsocketsInfo, commands, load_plugin


load_plugin("example_plugin")


@commands.on("echoimg {img}")
async def echoimg(img: Image, session: ContextSession):
    await session.send_message([img])


@commands.on("add {a} {b}")
async def add(a: int, b: int, session: ContextSession):
    await session.send_message(f"{a + b =}")


app = Entari(
    WebsocketsInfo(
        port=12345,
        path="foo"
    )
)

app.run()
