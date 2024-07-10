import re

from arclet.alconna import Alconna, AllParam, Args

from arclet.entari import (
    Session,
    MessageChain,
    MessageCreatedEvent,
    PluginMetadata,
    command,
    is_direct_message,
)
from arclet.entari.command import Match

__plugin_metadata__ = PluginMetadata(__file__)

disp_message = MessageCreatedEvent.dispatch()


@disp_message.on()
async def _(msg: MessageChain):
    content = msg.extract_plain_text()
    if re.match(r"(.{0,3})(上传|设定)(.{0,3})(上传|设定)(.{0,3})", content):
        return "上传设定的帮助是..."



from satori import select, Author


@disp_message.on(auxiliaries=[])
async def _(event: MessageCreatedEvent):
    print(event.content)
    if event.quote and (authors := select(event.quote, Author)):
        author = authors[0]
        reply_self = author.id == event.account.self_id


on_alconna = command.mount(Alconna("echo", Args["content?", AllParam]))


@on_alconna()
async def _(content: Match[MessageChain], session: Session):
    if content.available:
        await session.send(content.result)
        return

    await session.send(await session.prompt("请输入内容"))


@command.on("add {a} {b}")
async def add(a: int, b: int, session: Session):
    await session.send_message(f"{a + b =}")
