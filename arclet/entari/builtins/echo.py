from arclet.alconna import Alconna, AllParam, Args, CommandMeta

from arclet.entari import MessageChain, Session, command, metadata
from arclet.entari.command import Match

metadata(
    "echo",
    author=["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="Echo the content",
)


cmd = command.mount(Alconna("echo", Args["content?", AllParam], meta=CommandMeta("显示消息", compact=True)))


@cmd.handle
async def echo_handle(content: Match[MessageChain], session: Session):
    if content.available:
        return await session.send(content.result)


@cmd.on_execute()
async def echo_exec(content: Match[MessageChain]):
    if content.available:
        return content.result
