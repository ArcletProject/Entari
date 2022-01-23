from ....main.module import BaseModule, ModuleMetaComponent
from ....builtin.mah import VERIFY_CODE


class MessageModuleData(ModuleMetaComponent):
    identifier = VERIFY_CODE


class MessageModule(BaseModule):
    prefab_metadata = MessageModuleData
