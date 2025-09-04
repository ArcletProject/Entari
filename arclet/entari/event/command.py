from arclet.alconna import Alconna, Arparma
from arclet.letoderea import Contexts, Provider, Result, make_event

from ..message import MessageChain
from ..session import Session
from .base import Reply


@make_event(name="entari.event/command/execute")
class CommandExecute:
    message: str | MessageChain

    async def gather(self, context: Contexts):
        if isinstance(self.message, str):
            context["message"] = MessageChain(self.message)
        else:
            context["message"] = self.message

    class CommandProvider(Provider[MessageChain]):
        async def __call__(self, context: Contexts):
            return context.get("message")

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

    def check_result(self, value) -> Result[MessageChain] | None:
        if isinstance(value, MessageChain):
            return Result(value)


@make_event(name="entari.event/command/after_parse")
class CommandParse:
    """解析完命令后调用"""

    session: Session
    command: Alconna
    result: Arparma

    def check_result(self, value) -> Result[Arparma | bool] | None:
        if isinstance(value, Arparma | bool):
            return Result(value)
