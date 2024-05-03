from satori import Image

from arclet.entari import ContextSession, Entari, EntariCommands, WebsocketsInfo, load_plugin

commands = EntariCommands()


@commands.on("echoimg {img}")
async def echoimg(img: Image, session: ContextSession):
    await session.send_message([img])


load_plugin("example_plugin")

app = Entari(WebsocketsInfo(host="127.0.0.1", port=5140, path="satori"))

app.run()
