import asyncio
from typing import Type, List, Callable, Optional, Dict
from abc import ABCMeta
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.handler import await_exec_target
from .medium import BaseMedium
from ..security import UNKNOWN
from ..utilles import ModuleStatus
from .exceptions import DataMissing
from .event import BasicEvent
from .typings import TMProtocol, TProtocol, TData


class BaseModule(metaclass=ABCMeta):
    protocol: TProtocol
    medium_type: Type = TData
    identifier: int = UNKNOWN
    state: ModuleStatus = ModuleStatus.ACTIVATE_WAIT

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "medium_type"):
            cls.state = ModuleStatus.CLOSED
            raise DataMissing
        return super(BaseModule, cls).__new__(cls)

    def __init__(self, protocol: TProtocol):
        protocol.verify(self)
        self.protocol = protocol
        self.state = ModuleStatus.ESTABLISHED

    @property
    def __name__(self):
        return self.__class__.__name__

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; {', '.join([f'{k}={v}' for k, v in vars(self).items()])}>"
        )


class MediumModule(BaseModule):
    """因为对于注册的处理器来讲不需要用抽象方法去制定，所以直接写了"""
    protocol: TMProtocol
    medium_type: Type[BaseMedium]
    handlers: Dict[Type[BasicEvent], Subscriber] = {}
    __cache: List[Optional[List]] = []

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        if self.__cache:
            for er in self.__cache:
                self.handlers.setdefault(er[0], Subscriber(er[1]))
            self.__cache.clear()

    def new_handler(self, event_type, reaction: Optional[Callable] = None):
        def __wrapper(_reaction):
            self.handlers.setdefault(event_type.value, Subscriber(_reaction))
        if not reaction:
            return __wrapper
        __wrapper(reaction)

    @classmethod
    def prefab_handler(cls, event_type, reaction: Optional[Callable] = None):
        def __wrapper(_reaction):
            cls.__cache.append([event_type, _reaction])
        if not reaction:
            return __wrapper
        __wrapper(reaction)

    def parameter_generator(self, event_type: Type[BasicEvent], medium: BaseMedium):
        def __export():
            return event_type.param_export(
                Edoves=self.protocol.client,
                protocol=self.protocol,
                **{medium.__class__.__name__: medium},
                **{k: v for k, v in medium.__dict__.items() if k in medium.__annotations__}
            )
        return __export

    async def exec_handlers(self, medium: BaseMedium):
        if medium.__class__ != self.medium_type:
            return
        coroutine = [
            await_exec_target(
                target,
                self.parameter_generator(event_type, medium)
            )
            for event_type, target in self.handlers.items()
        ]
        results = await asyncio.gather(coroutine)
        for task in results:
            if task.exception().__class__.__name__ == "PropagationCancelled":
                break


