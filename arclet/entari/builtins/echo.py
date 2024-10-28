from arclet.alconna import Alconna, AllParam, Args, CommandMeta

from arclet.entari import MessageChain, Session, command, metadata
from arclet.entari.command import Match

metadata(__file__)


@command.mount(Alconna("echo", Args["content?", AllParam], meta=CommandMeta(compact=True)))
async def _(content: Match[MessageChain], session: Session):
    if content.available:
        return await session.send(content.result)
