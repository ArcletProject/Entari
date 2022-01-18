import asyncio
from typing import Type, Dict, Callable, Optional, Set

from .interact import InteractiveObject
from .typings import TProtocol, TMProtocol
from ..utilles import ModuleStatus
from ..utilles.security import UNKNOWN, IdentifierChecker, MIRAI_API_HTTP_DEFAULT
from ...letoderea.entities.delegate import EventDelegate, Subscriber
from ...letoderea.utils import run_always_await
from .behavior import BaseBehavior
from .event import BasicEvent
from .component import MetadataComponent, Component


class ModuleMetaComponent(MetadataComponent, metaclass=IdentifierChecker):
    io: "BaseModule"
    protocol: TProtocol
    identifier: str = MIRAI_API_HTTP_DEFAULT or UNKNOWN
    state: ModuleStatus = ModuleStatus.ACTIVATE_WAIT


class ModuleBehavior(BaseBehavior):
    io: "BaseModule"
    invoke_list: Set[str] = {}

    # def __init__(self, io: "BaseModule"):
    #     super().__init__(io)

    def activate(self):
        data = self.get_component(ModuleMetaComponent)
        data.protocol.verify(self.interactive_object)
        data.state = ModuleStatus.ESTABLISHED

    async def invoke(self, method_name: str, time: float):
        if method_name not in self.invoke_list:
            self.invoke_list.add(method_name)
            await asyncio.sleep(time)
            await run_always_await(self.__getattribute__(method_name))

    async def invoke_repeating(self, method_name: str, time: float, repeating_rate: float):
        if method_name not in self.invoke_list:
            self.invoke_list.add(method_name)
            await asyncio.sleep(time)
        while method_name in self.invoke_list:
            await run_always_await(self.__getattribute__(method_name))
            await asyncio.sleep(repeating_rate)

    def cancel_invoke(self, method_name: Optional[str] = None):
        if not method_name:
            self.invoke_list.clear()
        else:
            self.invoke_list.remove(method_name)

    def is_invoke(self, method_name: str):
        return method_name in self.invoke_list


class BaseModule(InteractiveObject):
    prefab_metadata = ModuleMetaComponent
    prefab_behavior = ModuleBehavior
    metadata: prefab_metadata
    behavior: prefab_behavior
    local_storage: Dict = {}

    def __init__(self, protocol: TProtocol):
        metadata = self.prefab_metadata(self)
        metadata.protocol = protocol
        super().__init__(metadata, self.prefab_behavior)

    @property
    def name(self):
        return self.__class__.__name__

    def change_behavior(self, behavior: Type[prefab_behavior]):
        self.behavior = behavior(self)

# ----
# MediumModule
# ----


class MediumHandlers(Component):
    io: "MediumModule"

    def add_handler(self, event_type: Type[BasicEvent], handler: Subscriber):
        _may_delegate = getattr(self, event_type.medium.type, None)
        if not _may_delegate:
            delegate = EventDelegate(event_type)
            delegate += handler
            self.__setattr__(event_type.medium.type, delegate)
        else:
            _may_delegate += handler

    def remove_handler(self, event_type: Type[BasicEvent]):
        delattr(self, event_type.medium.type)


class MediumModuleBehavior(ModuleBehavior):
    io: "MediumModule"

    def new_handler(self, event_type: Type[BasicEvent], *reaction: Callable):
        handlers = self.get_component(MediumHandlers)

        def __wrapper(_reaction):
            handlers.add_handler(event_type, Subscriber(_reaction))

        if not reaction:
            return __wrapper
        for r in reaction:
            __wrapper(r)

    async def handler_event(self, event: BasicEvent):
        handlers = self.get_component(MediumHandlers).handlers
        delegate = handlers.get(event.medium.type)
        await delegate.executor(event)


class MediumModule(BaseModule):
    """因为对于注册的处理器来讲不需要用抽象方法去制定，所以直接写了"""
    prefab_behavior = MediumModuleBehavior
    handlers: MediumHandlers

    __slots__ = ["handlers"]

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        self.handlers = MediumHandlers(self)
        for k, v in self.local_storage:
            self.get_component(MediumModuleBehavior).new_handler(k, *v)

    @classmethod
    def new_handler(__module_self__, event_type: Type[BasicEvent], *reaction: Callable):
        if __module_self__ is MediumModule:
            __module_self__.local_storage.setdefault(event_type, reaction)
        elif isinstance(__module_self__, MediumModule):
            return __module_self__.get_component(MediumModuleBehavior).new_handler(event_type, *reaction)

    async def import_event(self, event: BasicEvent):
        await self.get_component(MediumModuleBehavior).handler_event(event)
