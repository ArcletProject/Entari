import re

from arclet.entari import MessageCreatedEvent, Session, filter_, listen, metadata

metadata(
    name="管道命令",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="一个允许用户通过管道符连接多个命令的插件。",
    readme="""
# 管道命令

该插件提供了一个特殊的 `$$` 命令，允许用户通过管道符（默认为 `|`）连接多个命令。
用户可以输入类似于 `$$ command1 | command2 | command3` 的命令，插件会依次执行这些命令，
并将前一个命令的输出作为下一个命令的输入。

## 使用

直接输入命令： `$$ command1 | command2 | command3`，即可执行多个命令并获取最终输出。
""",
    config=None,
)


@listen(MessageCreatedEvent).if_(filter_(lambda sess: sess.content.startswith("$$")))
async def pipe(sess: Session):
    content = sess.content[2:]
    if not content:
        return "请输入要执行的命令。"
    parts = re.split(r"\s+\|\s+", content.strip())
    if not parts:
        return "请输入有效的命令。"
    ans = await sess.execute(parts[0])
    if len(parts) == 1:
        await sess.send(ans if ans else "命令执行完成，但没有输出。")
        return
    for part in parts[1:]:
        if not part.strip():
            continue
        cmd = f"{part} {ans}" if ans else part
        _ans = await sess.execute(cmd)
        if _ans is not None:
            ans = _ans
    if ans is None:
        return "命令执行完成，但没有输出。"
    await sess.send(ans)
