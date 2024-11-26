from arclet.alconna import Alconna, AllParam, Args, CommandMeta

from arclet.entari import MessageChain, Session, command, metadata
from arclet.entari.command import Match

metadata(__file__)


cmd = command.mount(Alconna("echo", Args["content?", AllParam], meta=CommandMeta(compact=True)))


@cmd.handle
async def _(content: Match[MessageChain], session: Session):
    if content.available:
        return await session.send(content.result)


@cmd.on_execute()
async def _(content: Match[MessageChain]):
    if content.available:
        return content.result
