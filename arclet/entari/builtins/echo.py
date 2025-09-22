from arclet.alconna import Arparma

from arclet.entari import MessageChain, command, metadata
from arclet.entari.command import Match

metadata(
    "Echo",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="Echo the content",
    readme="""
# Echo

该插件用于回显消息。

## 使用

- 基本用法: `echo <内容>`
- 发送转义消息: `echo -e <内容>`，例如 `echo -e @user` 会发送 `<at id=user>` 文本
- 发送反转义消息: `echo -E <内容>`，例如 `echo -E <at id=user>` 会发送 `@user` 元素
""",
    config=None,
)


@(
    command.command("echo <...content>", "显示消息")
    .option("escape", "-e|--escape # 发送转义消息")
    .option("unescape", "-E|--unescape # 发送反转义消息")
    .config(compact=True)
)
async def echo(content: Match[MessageChain], arp: Arparma):
    if arp.find("unescape"):
        return MessageChain.of(content.result.extract_plain_text())
    elif arp.find("escape"):
        return str(content.result)
    else:
        return content.result
