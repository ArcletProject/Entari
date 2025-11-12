from arclet.alconna import Alconna, Arparma
from arclet.letoderea import Contexts, Result, make_event, provide

from ..message import MessageChain
from ..session import Session
from .base import Reply


@make_event(name="entari.event/command/execute")
class CommandExecute:
    message: str | MessageChain

    async def gather(self, context: Contexts):
        if isinstance(self.message, str):
            context["$message"] = MessageChain(self.message)
        else:
            context["$message"] = self.message

    providers = [provide(MessageChain, call="$message")]

    def check_result(self, value) -> Result[str | MessageChain] | None:
        if isinstance(value, str | MessageChain):
            return Result(value)


@make_event(name="entari.event/command/output")
class CommandOutput:
    """依据输出信息的类型，将字符串转换为消息对象以便发送。"""

    session: Session
    command: Alconna
    type: str
    content: str

    async def gather(self, context: Contexts):
        context["$session"] = self.session
        context["$out_command"] = self.command
        context["$out_content"] = self.content

    providers = [
        provide(Alconna, call="$out_command"),
        provide(str, call="$out_content"),
    ]

    def check_result(self, value) -> Result[str | bool | MessageChain] | None:
        if isinstance(value, str | bool | MessageChain):
            return Result(value)


@make_event(name="entari.event/command/before_parse")
class CommandReceive:
    """尝试解析命令时调用"""

    session: Session
    command: Alconna
    content: MessageChain
    reply: Reply | None = None

    async def gather(self, context: Contexts):
        context["$session"] = self.session
        context["$cmd_content"] = self.content
        context["$cmd_command"] = self.command
        if self.reply:
            context["$cmd_reply"] = self.reply

    providers = [
        provide(MessageChain, call="$cmd_content"),
        provide(Alconna, call="$cmd_command"),
        provide(Reply, call="$cmd_reply"),
    ]

    def check_result(self, value) -> Result[MessageChain] | None:
        if isinstance(value, MessageChain):
            return Result(value)


@make_event(name="entari.event/command/after_parse")
class CommandParse:
    """解析完命令后调用"""

    session: Session
    command: Alconna
    result: Arparma

    async def gather(self, context: Contexts):
        context["$session"] = self.session
        context["$parsed_command"] = self.command
        context["$parsed_result"] = self.result

    providers = [
        provide(Alconna, call="$parsed_command"),
        provide(Arparma, call="$parsed_result"),
    ]

    def check_result(self, value) -> Result[Arparma | bool] | None:
        if isinstance(value, Arparma | bool):
            return Result(value)
