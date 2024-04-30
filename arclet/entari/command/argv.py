from arclet.alconna import Argv, argv_config, set_default_argv_type
from satori import Text

from ..message import MessageChain


class MessageArgv(Argv[MessageChain]):
    @staticmethod
    def generate_token(data: list) -> int:
        return hash("".join(i.__repr__() for i in data))


set_default_argv_type(MessageArgv)

argv_config(
    MessageArgv,
    filter_out=[],
    to_text=lambda x: x.text if x.__class__ is Text else None,
    converter=lambda x: MessageChain(x),
)
