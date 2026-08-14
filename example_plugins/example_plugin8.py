from arclet.entari.filter.message import startswith, regexmatch, regex_origin
from arclet.entari import MessageCreatedEvent, MessageChain, Session, listen, Image, Text, User


@listen(MessageCreatedEvent).if_(startswith("!hello"))
async def hello_listener1(sess: Session, message: MessageChain, user: User):
    await sess.send(f"Hello! This is a response from the hello_listener. {user}")
    await sess.send(message)


@listen(MessageCreatedEvent).if_(startswith(Image, include=True))
async def image_listener(sess: Session, message: MessageChain):
    await sess.send("Hello! This is a response from the image_listener.")
    await sess.send(message)


@listen(MessageCreatedEvent).if_(startswith("!world", bind="world"))
async def hello_listener2(sess: Session, message: MessageChain, world: MessageChain):
    await sess.send("Hello! This is a response from the hello_listener2.")
    await sess.send(message)
    await sess.send(world)


@listen(MessageCreatedEvent).if_(regexmatch(r"test (\d+)", flags=2))
async def regex_listener(
    sess: Session,
    message: MessageChain,
    match = regex_origin(),
    group1: str = regex_origin().group(1),
    dicts: dict = regex_origin().groupdict(),
):
    await sess.send(f"Hello! This is a response from the regex_listener. You said: {message}")
    await sess.send(f"Matched: {Text(str(match))}")
    await sess.send(f"Matched group 1: {group1}")
    await sess.send(f"Matched dicts: {dicts}")
