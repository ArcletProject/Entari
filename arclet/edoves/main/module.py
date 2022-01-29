import asyncio
from typing import Type, Dict, Callable, Optional, Set, List, TypedDict
from arclet.letoderea.utils import Condition_T
from arclet.letoderea.entities.delegate import EventDelegate, Subscriber
from arclet.letoderea.utils import run_always_await

from .interact import InteractiveObject
from .protocol import ModuleProtocol
from ..utilles import IOStatus
from ..utilles.security import UNKNOWN, VerifyCodeChecker
from .behavior import BaseBehavior
from .event import EdovesBasicEvent
from .component import MetadataComponent, Component


class ModuleMetaComponent(MetadataComponent, metaclass=VerifyCodeChecker):
    io: "BaseModule"
    protocol: ModuleProtocol
    verify_code: str = UNKNOWN
    name: str
    usage: str
    description: str


class _Handler(TypedDict):
    delegate: EventDelegate
    condition: List[Condition_T]


class MediumHandlers(Component):
    io: "BaseModule"
    storage: Dict[Type[EdovesBasicEvent], _Handler]

    def __init__(self, io: "BaseModule"):
        super(MediumHandlers, self).__init__(io)
        self.storage = {}

    def add_handlers(
            self,
            event_type: Type[EdovesBasicEvent],
            handlers: List[Subscriber],
            conditions: Optional[List[Condition_T]] = None
    ):
        _may_delegate = self.storage.get(event_type)
        if not _may_delegate:
            delegate = EventDelegate(event_type)
            delegate += handlers
            self.storage.setdefault(event_type, {'delegate': delegate, 'condition': conditions})
        else:
            _may_delegate['delegate'] += handlers
            _may_delegate['condition'].extend(conditions)

    def remove_handler(self, event_type: Type[EdovesBasicEvent]):
        del self.storage[event_type]

    def __repr__(self):
        return (
            f"[{self.__class__.__name__}: " +
            f"{' '.join([f'{k}={v}' for k, v in self.storage.items()])}]"
        )


class ModuleBehavior(BaseBehavior):
    io: "BaseModule"
    invoke_list: Set[str] = {}

    def activate(self):
        data = self.get_component(ModuleMetaComponent)
        data.protocol.verify(self.interactive_object)
        data.state = IOStatus.ESTABLISHED

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

    def add_handlers(
            self, event_type: Type[EdovesBasicEvent],
            *reaction: Callable,
            condition: Optional[List[Condition_T]] = None
    ):
        handlers = self.get_component(MediumHandlers)

        def __wrapper(_reaction):
            if isinstance(_reaction, Callable):
                handlers.add_handlers(event_type, [Subscriber(_reaction)], conditions=condition)
            else:
                handlers.add_handlers(
                    event_type,
                    [Subscriber(_r) for _r in _reaction],
                    conditions=condition
                )

        if not reaction:
            return __wrapper
        __wrapper(reaction)

    async def handler_event(self, event: EdovesBasicEvent):
        handler = self.get_component(MediumHandlers).storage.get(event.__class__)
        if not handler:
            return
        self.io.metadata.state = IOStatus.PROCESSING
        if handler['condition']:
            if not all([condition.judge(event) for condition in handler['condition']]):
                self.io.metadata.state = IOStatus.ESTABLISHED
                return
        await handler['delegate'].executor(event)
        self.io.metadata.state = IOStatus.ESTABLISHED


class BaseModule(InteractiveObject):
    prefab_metadata = ModuleMetaComponent
    prefab_behavior = ModuleBehavior
    prefab_handlers = MediumHandlers
    metadata: prefab_metadata
    behavior: prefab_behavior
    handlers: MediumHandlers
    local_storage: Dict = {}

    __slots__ = ["handlers"]

    def __init__(self, protocol: ModuleProtocol):
        metadata = self.prefab_metadata(self)
        metadata.protocol = protocol
        if not getattr(metadata, "identifier", None):
            metadata.identifier = str(self.__class__)
        super().__init__(metadata)
        self.handlers = MediumHandlers(self)
        if self.local_storage.get(self.__class__):
            for k, v in self.local_storage.pop(self.__class__).items():
                self.get_component(self.prefab_behavior).add_handlers(k, *v[0], condition=v[1])

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
            condition: Optional[List[Condition_T]] = None
    ):
        if not __module_self__.local_storage.get(__module_self__):
            __module_self__.local_storage.setdefault(__module_self__, {})
        __module_self__.local_storage[__module_self__].setdefault(event_type, [reaction, condition])

    def add_handler(
            __module_self__,
            event_type: Type[EdovesBasicEvent],
            *reaction: Callable,
            condition: Optional[List[Condition_T]] = None
    ):
        try:
            return __module_self__.behavior.add_handlers(event_type, *reaction, condition=condition)
        except AttributeError:
            if not __module_self__.local_storage.get(__module_self__.__class__):
                __module_self__.local_storage.setdefault(__module_self__.__class__, {})
            __module_self__.local_storage[__module_self__.__class__].setdefault(event_type, [reaction, condition])

    async def import_event(self, event: EdovesBasicEvent):
        await self.get_component(ModuleBehavior).handler_event(event)
