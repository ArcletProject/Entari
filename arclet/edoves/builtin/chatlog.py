from .medium import Message
from ..main.monomer import Monomer
from ..main.module import BaseModule, ModuleMetaComponent
from ..main.typings import TMProtocol
from ..utilles.security import EDOVES_DEFAULT
from .event.message import AllMessage


def log_message(module: BaseModule, message: Message, purveyor: Monomer):
    edoves = module.metadata.protocol.scene.edoves
    if purveyor.prime_tag == "Member":
        edoves.logger.log(
            module.metadata.log_level,
            module.metadata.group_message_log_format.format(
                group_name=list(purveyor.parents.values())[0].metadata.name,
                group_id=list(purveyor.parents.values())[0].metadata.identifier,
                member_id=purveyor.metadata.identifier,
                member_name=purveyor.metadata.name,
                bot_id=edoves.self.metadata.identifier,
                message_string=message.content.to_text().__repr__(),
            ),
        )
    elif purveyor.prime_tag == "Friend":
        edoves.logger.log(
            module.metadata.log_level,
            module.metadata.friend_message_log_format.format(
                friend_id=purveyor.metadata.identifier,
                friend_name=purveyor.metadata.name,
                bot_id=edoves.self.metadata.identifier,
                message_string=message.content.to_text().__repr__(),
            ),
        )


class ChatLogData(ModuleMetaComponent):
    identifier: str = EDOVES_DEFAULT
    log_level: str = "INFO"
    group_message_log_format: str = (
        "{bot_id}: [{group_name}({group_id})] {member_name}({member_id}) -> {message_string}" )
    friend_message_log_format: str = "{bot_id}: [{friend_name}({friend_id})] -> {message_string}"
    other_client_message_log_format: str = "{bot_id}: [{platform_name}({platform_id})] -> {message_string}"


class ChatLogModule(BaseModule):
    prefab_metadata = ChatLogData

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        self.new_handler(AllMessage, log_message)
