from arclet.entari import Author, BasicConfModel, MessageChain, metadata, plugin
from arclet.entari.event.command import CommandReceive


class Config(BasicConfModel):
    sep: str = " "
    """合并消息的分隔符，默认为空格"""


metadata(
    name="引用消息合并",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="一个可以修改指令解析使得合并消息被放入指令体的插件。",
    readme="""
# 引用消息合并

用于将消息事件中的回复指向的原消息合并到当前消息中作为一部分参数

""",
    config=Config,
)

_conf = plugin.get_config(Config)


@plugin.listen(CommandReceive)
async def merge_quote(event: CommandReceive):
    """将引用消息合并到指令体中"""
    if event.reply and event.reply.quote.children:
        event.content = event.content + _conf.sep + MessageChain(event.reply.quote.children).exclude(Author)
