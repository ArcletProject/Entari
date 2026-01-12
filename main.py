from satori import Image

from arclet.entari import Session, Entari, command, load_plugin, unload_plugin, enable_plugin, disable_plugin


@command.on("echoimg {img}")
async def echoimg(img: Image, session: Session):
    await session.send_message([img])


app = Entari.load("example.yml")


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


@command.on("enable {plugin}")
async def enable(plugin: str, session: Session):
    if enable_plugin(plugin):
        await session.send_message(f"Enabled {plugin}")
    else:
        await session.send_message(f"Failed to enable {plugin}")


@command.on("disable {plugin}")
async def disable(plugin: str, session: Session):
    if disable_plugin(plugin):
        await session.send_message(f"Disabled {plugin}")
    else:
        await session.send_message(f"Failed to disable {plugin}")


app.run()
