from arclet.edoves.main.interact.module import BaseModule, ModuleMetaComponent

from .. import VERIFY_CODE


class MessageModuleData(ModuleMetaComponent):
    verify_code = VERIFY_CODE
    identifier = "edoves.mirai-api-http.test_message_module"
    name = "BuiltinMessageModule"


class MessageModule(BaseModule):
    prefab_metadata = MessageModuleData
