from .medium import Message
from ..main.monomer import Monomer
from ..main.module import BaseModule, ModuleMetaComponent
from ..main.typings import TMProtocol
from ..utilles.security import EDOVES_DEFAULT
from .event.message import MessageReceived


def log_message(module: BaseModule, message: Message, purveyor: Monomer):
    scene = module.metadata.protocol.scene
    if purveyor.prime_tag == "Member":
        scene.edoves.logger.log(
            module.metadata.log_level,
            module.metadata.group_message_log_format.format(
                scene_name=scene.scene_name,
                group_name=purveyor.current_group.metadata.name,
                group_id=purveyor.current_group.metadata.identifier,
                member_id=purveyor.metadata.identifier,
                member_name=purveyor.metadata.name,
                bot_id=scene.protagonist.metadata.identifier,
                message_string=message.content.to_text().__repr__(),
            ),
        )
    elif purveyor.prime_tag == "Friend":
        scene.edoves.logger.log(
            module.metadata.log_level,
            module.metadata.friend_message_log_format.format(
                scene_name=scene.scene_name,
                friend_id=purveyor.metadata.identifier,
                friend_name=purveyor.metadata.name,
                bot_id=scene.protagonist.metadata.identifier,
                message_string=message.content.to_text().__repr__(),
            ),
        )


class ChatLogData(ModuleMetaComponent):
    verify_code: str = EDOVES_DEFAULT
    identifier = "BuiltinChatLog"
    log_level: str = "INFO"
    group_message_log_format: str = (
        "{scene_name} >>> {bot_id}: [{group_name}({group_id})] {member_name}({member_id}) -> {message_string}")
    friend_message_log_format: str = "{scene_name} >>> {bot_id}: [{friend_name}({friend_id})] -> {message_string}"
    other_client_message_log_format: str = "{scene_name} >>> {bot_id}: [{platform_name}({platform_id})] -> {message_string}"


class ChatLogModule(BaseModule):
    prefab_metadata = ChatLogData

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        self.add_handler(MessageReceived, log_message)
