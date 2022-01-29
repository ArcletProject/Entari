from ....main.module import BaseModule, ModuleMetaComponent
from ....builtin.mah import VERIFY_CODE


class MessageModuleData(ModuleMetaComponent):
    verify_code = VERIFY_CODE
    identifier = "BuiltinMessageModule"


class MessageModule(BaseModule):
    prefab_metadata = MessageModuleData
