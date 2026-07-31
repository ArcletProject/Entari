from arclet.entari.filter.message import startswith
from arclet.entari import MessageCreatedEvent, MessageChain, Session, listen, Image


@listen(MessageCreatedEvent)
@startswith("!hello")
async def hello_listener1(sess: Session, message: MessageChain):
    await sess.send("Hello! This is a response from the hello_listener.")
    await sess.send(message)


@listen(MessageCreatedEvent)
@startswith(Image, include=True)
async def image_listener(sess: Session, message: MessageChain):
    await sess.send("Hello! This is a response from the image_listener.")
    await sess.send(message)


@listen(MessageCreatedEvent)
@startswith("!world", bind="world")
async def hello_listener2(sess: Session, message: MessageChain, world: MessageChain):
    await sess.send("Hello! This is a response from the hello_listener2.")
    await sess.send(message)
    await sess.send(world)
