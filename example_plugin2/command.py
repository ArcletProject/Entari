from arclet.alconna import Alconna, Args, AllParam

from arclet.entari import command, MessageChain, Session
from arclet.entari.command import Match

on_alc = command.mount(Alconna("echo1", Args["content?", AllParam]))


@on_alc
async def _(content: Match[MessageChain], session: Session):
    if content.available:
        await session.send(content.result)
        return
    resp = await session.prompt("请输入内容")
    if resp:
        await session.send(resp)
