from satori import Image

from arclet.entari import Session, Entari, command, WebsocketsInfo, load_plugin, dispose_plugin


@command.on("echoimg {img}")
async def echoimg(img: Image, session: Session):
    await session.send_message([img])


load_plugin("example_plugin")

app = Entari(WebsocketsInfo(host="127.0.0.1", port=5140, path="satori"))


@command.on("load {plugin}")
async def load(plugin: str, session: Session):
    if load_plugin(plugin):
        await session.send_message(f"Loaded {plugin}")
    else:
        await session.send_message(f"Failed to load {plugin}")


@command.on("unload {plugin}")
async def unload(plugin: str, session: Session):
    if dispose_plugin(plugin):
        await session.send_message(f"Unloaded {plugin}")
    else:
        await session.send_message(f"Failed to unload {plugin}")

app.run()
