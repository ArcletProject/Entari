from arclet.alconna import Arparma

from arclet.entari import MessageChain, command, metadata
from arclet.entari.command import Match

metadata(
    "echo",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="Echo the content",
)


@(
    command.command("echo <...content>", "显示消息")
    .option("escape", "-e|--escape # 发送转义消息")
    .option("unescape", "-E|--unescape # 发送反转义消息")
    .config(compact=True)
)
def echo(content: Match[MessageChain], arp: Arparma):
    if arp.find("unescape"):
        return MessageChain.of(content.result.extract_plain_text())
    elif arp.find("escape"):
        return str(content.result)
    else:
        return content.result
