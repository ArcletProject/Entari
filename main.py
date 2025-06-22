from satori import Image

from arclet.entari import Session, Entari, command, load_plugin, unload_plugin


@command.on("echoimg {img}")
async def echoimg(img: Image, session: Session):
    await session.send_message([img])


app = Entari.load("example2.yml")


@command.on("load {plugin}")
async def load(plugin: str, session: Session):
    if load_plugin(plugin):
        await session.send_message(f"Loaded {plugin}")
    else:
        await session.send_message(f"Failed to load {plugin}")


@command.on("unload {plugin}")
async def unload(plugin: str, session: Session):
    if unload_plugin(plugin):
        await session.send_message(f"Unloaded {plugin}")
    else:
        await session.send_message(f"Failed to unload {plugin}")

app.run()
