from arclet.edoves.main.event import EdovesBasicEvent, ctx_module, edoves_instance
from ..medium import Notice


class _NoticeEvent(EdovesBasicEvent):

    __field__: str

    def get_params(self):
        return self.param_export(
            edoves=edoves_instance.get(),
            module=ctx_module.get(),
            medium=self.medium,
            **self.medium_vars(),
            **{self.__field__: getattr(self, self.__field__, None)}
        )


class NoticeMe(_NoticeEvent):
    medium: Notice


class MonomerMetadataUpdate(_NoticeEvent):
    """数据更改, 比如名字, 头衔等等"""
    action: str
    medium: Notice
    __field__ = "action"


class MonomerStatusUpdate(_NoticeEvent):
    """状态更改, 比如权限、是否被禁言, 等等"""
    action: str
    medium: Notice
    __field__ = "action"


class RelationshipSetup(_NoticeEvent):
    """关系建立"""
    relationship: str
    medium: Notice
    __field__ = "relationship"


class RelationshipTerminate(_NoticeEvent):
    """主动解除关系"""
    relationship: str
    medium: Notice
    __field__ = "relationship"


class RelationshipSevered(_NoticeEvent):
    """被动解除关系"""
    relationship: str
    medium: Notice
    __field__ = "relationship"
