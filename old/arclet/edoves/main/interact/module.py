import asyncio
from typing import Callable, Dict, List, Optional, Set, Type, Union

from arclet.letoderea.entities.auxiliary import BaseAuxiliary
from arclet.letoderea.entities.delegate import EventDelegate, Subscriber
from arclet.letoderea.utils import TEvent, run_always_await, search_event

from . import InteractiveObject
from ..component import Component, MetadataComponent
from ..component.behavior import BaseBehavior
from ..context import ctx_event, ctx_module
from ..event import EdovesBasicEvent
from ..medium import BaseMedium
from ..typings import TProtocol
from ..utilles import IOStatus
from ..utilles.security import UNKNOWN, VerifyCodeChecker


class ModuleMetaComponent(MetadataComponent, VerifyCodeChecker):
    io: "BaseModule"
    verify_code: str = UNKNOWN
    name: str
    usage: str
    description: str
    author: str


class MediumHandlers(Component):
    io: "BaseModule"
    primary_event_delegate: EventDelegate
    delegates: List[EventDelegate]

    def __init__(self, io: "BaseModule"):
        super(MediumHandlers, self).__init__(io)
        self.delegates = []

    def set_primary_delegate(self, delegate: EventDelegate) -> None:
        raise NotImplementedError

    def add_delegate(self, delegate: EventDelegate) -> None:
        """
        将delegate添加到delegates中
        应当保证同priority同event的delegate只能有一个
        """
        if self.delegates:
            last_delegate = self.delegates[-1]
            if (
                last_delegate.bind_event == delegate.bind_event
                and last_delegate.priority == delegate.priority
            ):
                last_delegate += delegate.subscribers
        self.delegates.append(delegate)

    def remove_delegate(self, target: Union[TEvent, EventDelegate]) -> None:
        if isinstance(target, EventDelegate):
            self.delegates.remove(target)
        else:
            delegates = self.require(target)
            for delegate in delegates:
                self.delegates.remove(delegate)

    def require(
        self,
        event: Union[str, TEvent],
        priority: Optional[int] = None,
    ) -> Optional[Union[EventDelegate, List[EventDelegate]]]:
        """
        依据event名称或者event对象，返回对应的delegate
        在每个publisher中可以存在多个delegate，利用priority进行排序
        但是同priority同event的delegate只能有一个
        """
        _delegates = [delegate for delegate in self.delegates if delegate.bind_event == event]
        if not _delegates:
            return None
        if priority:
            for delegate in filter(lambda d: d.priority == priority, _delegates):
                return delegate
        return _delegates

    def add_handlers(self, event_type: Type[EdovesBasicEvent], handlers: List[Subscriber]):
        delegate = EventDelegate(event_type)
        delegate += handlers
        self.add_delegate(delegate)

    def remove_handler(self, event_type: Type[EdovesBasicEvent]):
        self.remove_handler(event_type)

    def __repr__(self):
        return f"[{self.__class__.__name__}: " + f"{len(self.delegates)} delegates]"


class ModuleBehavior(BaseBehavior):
    io: "BaseModule"
    invoke_list: Set[str] = {}

    def activate(self):
        data = self.get_component(ModuleMetaComponent)
        self.interactive_object.protocol.verify(self.interactive_object)
        data.state = IOStatus.ESTABLISHED

    async def invoke(self, method_name: str, time: float):
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

    def add_handlers(
        self,
        event_type: Type[EdovesBasicEvent],
        *reaction: Callable,
        auxiliaries: Optional[List[BaseAuxiliary]] = None,
    ):
        handlers = self.get_component(MediumHandlers)

        def __wrapper(_reaction):
            if isinstance(_reaction, Callable):
                handlers.add_handlers(event_type, [Subscriber(_reaction, auxiliaries=auxiliaries)])
            else:
                handlers.add_handlers(
                    event_type,
                    [Subscriber(_r, auxiliaries=auxiliaries) for _r in _reaction],
                )

        if not reaction:
            return __wrapper
        __wrapper(reaction)

    async def handler_medium(
        self,
        medium: Optional[BaseMedium] = None,
        medium_type: Optional[BaseMedium] = None,
        event_type: Optional[Union[str, Type[EdovesBasicEvent]]] = None,
        **kwargs,
    ):
        if not medium:
            medium = await self.io.protocol.screen.get(medium_type, **kwargs)
        if event_type:
            if isinstance(event_type, str):
                event = search_event(event_type)(medium=medium, **kwargs)
            else:
                event = event_type(medium=medium, **kwargs)
        else:
            event = ctx_event.get()
        await self.handler_event(event)

    async def handler_event(self, event: EdovesBasicEvent):
        delegates = self.get_component(MediumHandlers).require(event.__class__)
        if not delegates:
            return
        self.io.metadata.state = IOStatus.PROCESSING
        with ctx_module.use(self.io):
            await self.io.protocol.screen.edoves.event_system.delegate_exec(delegates, event)
            self.io.metadata.state = IOStatus.ESTABLISHED


class BaseModule(InteractiveObject):
    prefab_metadata = ModuleMetaComponent
    prefab_behavior = ModuleBehavior
    prefab_handlers = MediumHandlers
    metadata: prefab_metadata
    behavior: prefab_behavior
    handlers: prefab_handlers
    local_storage: Dict = {}

    __slots__ = ["handlers"]

    def __init__(self, protocol: TProtocol):
        self.protocol = protocol
        metadata = self.prefab_metadata(self)
        if not hasattr(metadata, "identifier"):
            metadata.identifier = f"{self.__class__.__module__}.{self.__class__.__qualname__}"
        super().__init__(metadata)
        self.handlers = MediumHandlers(self)
        if self.local_storage.get(self.__class__):
            hds = self.local_storage.pop(self.__class__)
            for hd in hds:
                self.get_component(self.prefab_behavior).add_handlers(hd[0], *hd[1][0], auxiliaries=hd[1][1])

    @property
    def name(self):
        return getattr(self.metadata, "name", self.__class__.__name__)

    @property
    def usage(self):
        return getattr(self.metadata, "usage", None)

    @property
    def description(self):
        return getattr(self.metadata, "description", None)

    def change_behavior(self, behavior: Type[prefab_behavior]):
        self.behavior = behavior(self)

    @classmethod
    def inject_handler(
        __module_self__,
        event_type: Type[EdovesBasicEvent],
        *reaction: Callable,
        auxiliaries: Optional[List[BaseAuxiliary]] = None,
    ):
        if not __module_self__.local_storage.get(__module_self__):
            __module_self__.local_storage.setdefault(__module_self__, [])
        __module_self__.local_storage[__module_self__].append([event_type, [reaction, auxiliaries]])

    def add_handler(
        __module_self__,
        event_type: Type[EdovesBasicEvent],
        *reaction: Callable,
        auxiliaries: Optional[List[BaseAuxiliary]] = None,
    ):
        try:
            return __module_self__.behavior.add_handlers(event_type, *reaction, auxiliaries=auxiliaries)
        except AttributeError:
            if not __module_self__.local_storage.get(__module_self__.__class__):
                __module_self__.local_storage.setdefault(__module_self__.__class__, [])
            __module_self__.local_storage[__module_self__.__class__].append(
                [event_type, [reaction, auxiliaries]]
            )
