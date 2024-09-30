import re
import sys

from arclet.alconna import Alconna, AllParam, Args

from arclet.entari import (
    Session,
    MessageChain,
    MessageCreatedEvent,
    Plugin,
    command,
    is_public_message,
    bind,
    metadata,
    keeping
)
from arclet.entari.command import Match

metadata(__file__)

plug = Plugin.current()


@plug.on_prepare
async def prepare():
    print("example: Preparing")


@plug.on_cleanup
async def cleanup():
    print("example: Cleanup")


disp_message = MessageCreatedEvent.dispatch()


@disp_message
@bind(is_public_message)
async def _(msg: MessageChain, session: Session):
    content = msg.extract_plain_text()
    if re.match(r"(.{0,3})(上传|设定)(.{0,3})(上传|设定)(.{0,3})", content):
        return await session.send("上传设定的帮助是...")


disp_message1 = plug.dispatch(MessageCreatedEvent)


from satori import select, Author


@disp_message1.on(auxiliaries=[is_public_message])
async def _(event: MessageCreatedEvent):
    if event.quote and (authors := select(event.quote, Author)):
        author = authors[0]
        reply_self = author.id == event.account.self_id
        print(reply_self)
        print(event.content)


on_alc = command.mount(Alconna("echo", Args["content?", AllParam]))


@on_alc
async def _(content: Match[MessageChain], session: Session):
    if content.available:
        await session.send(content.result)
        return

    await session.send(await session.prompt("请输入内容"))


@command.on("add {a} {b}")
async def add(a: int, b: int, session: Session):
    await session.send_message(f"{a + b =}")


kept_data = keeping("foo", [], lambda x: x.clear())


@command.on("append {data}")
async def append(data: str, session: Session):
    kept_data.append(data)
    await session.send_message(f"Appended {data}")


@command.on("show")
async def show(session: Session):
    await session.send_message(f"Data: {kept_data}")

TEST = 5

print([*Plugin.current().dispatchers.keys()])
print(Plugin.current().submodules)
print("example_plugin not in sys.modules (expect True):", "example_plugin" not in sys.modules)
