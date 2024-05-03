from arclet.alconna import Alconna, AllParam, Args

from arclet.entari import (
    ContextSession,
    EntariCommands,
    MessageChain,
    MessageCreatedEvent,
    Plugin,
    is_direct_message,
)
from arclet.entari.command import Match

plug = Plugin()

disp_message = plug.dispatch(MessageCreatedEvent)


@disp_message.on(auxiliaries=[])
async def _(event: MessageCreatedEvent):
    print(event.content)


on_alconna = plug.mount(Alconna("echo", Args["content?", AllParam]))


@on_alconna.on()
async def _(content: Match[MessageChain], session: ContextSession):
    if content.available:
        await session.send(content.result)
        return

    await session.send(await session.prompt("请输入内容"))


commands = EntariCommands.current()


@commands.on("add {a} {b}")
async def add(a: int, b: int, session: ContextSession):
    await session.send_message(f"{a + b =}")
