from arclet.edoves.main.module import BaseModule, ModuleMetaComponent
from .. import VERIFY_CODE


class MessageModuleData(ModuleMetaComponent):
    verify_code = VERIFY_CODE
    identifier = "BuiltinMessageModule"


class MessageModule(BaseModule):
    prefab_metadata = MessageModuleData
