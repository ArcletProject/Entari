from asyncio import PriorityQueue
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, TypeVar, Union

from arclet.letoderea.utils import search_event

from .context import ctx_event, ctx_monomer, current_scene, edoves_instance
from .event import EdovesBasicEvent
from .medium import BaseMedium, MediumObserver
from .utilles import IOStatus, MediumStatus

TM = TypeVar("TM", bound=BaseMedium)

if TYPE_CHECKING:
    from . import Edoves
    from .interact import InteractiveObject


class Screen:
    edoves: "Edoves"
    medium_call_list: Dict[int, MediumObserver]
    medium_done_list: Dict[int, MediumObserver]
    medium_queue: PriorityQueue

    def __init__(self, edoves: "Edoves"):
        self.edoves = edoves
        self.medium_call_list = {}
        self.medium_done_list = {}
        self.medium_queue = PriorityQueue()

    async def push(self, medium: TM, in_time: bool = False):
        await self.medium_queue.put(medium)
        medium.status = MediumStatus.POSTING
        call = MediumObserver(medium, self.edoves.loop)
        self.medium_call_list[medium.mid] = call
        if in_time:
            await self.broadcast(medium.type)
        return call

    async def get(self, medium_type: Optional[Type[TM]] = None, **kwargs) -> TM:
        medium: TM = await self.medium_queue.get()
        if medium_type and not isinstance(medium, medium_type):
            medium = medium_type().create(medium.purveyor, medium.content, **kwargs)
        self.medium_done_list.setdefault(medium.mid, self.medium_call_list.pop(medium.mid))
        medium.status = MediumStatus.HANDLING
        return medium

    async def post(self, medium: TM, target: "InteractiveObject", **kwargs):
        call = MediumObserver(medium, self.edoves.loop)
        medium.status = MediumStatus.HANDLING
        self.medium_done_list.setdefault(medium.mid, call)
        await target.behavior.handler_medium(medium, **kwargs)
        return call

    def set_call(self, mid: int, result: Any):
        if mid in self.medium_done_list:
            call = self.medium_done_list.pop(mid)
            call.set_result(result)

    async def broadcast(
        self, event_type: Union[str, Type[EdovesBasicEvent]], medium_type: Optional[Type[TM]] = None, **kwargs
    ):
        evt = event_type if isinstance(event_type, str) else event_type.__class__.__name__
        medium = await self.get(medium_type=medium_type, event_type=evt)
        protocol = medium.purveyor.protocol
        io_list = list(protocol.current_scene.all_io.values())
        if isinstance(event_type, str):
            event = search_event(event_type)(medium=medium, **kwargs)
        else:
            event = event_type(medium=medium, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(edoves_instance.use(self.edoves))
            stack.enter_context(current_scene.use(protocol.current_scene))
            stack.enter_context(ctx_event.use(event))
            stack.enter_context(ctx_monomer.use(event.medium.purveyor))
            self.edoves.event_system.event_publish(event)
            protocol.record_event(medium, event.__class__.__name__)
            for io in filter(
                lambda x: x.metadata.state in (IOStatus.ESTABLISHED, IOStatus.MEDIUM_GET_WAIT), io_list
            ):
                self.edoves.loop.create_task(
                    io.behavior.handler_medium(medium=medium, medium_type=medium_type, **kwargs),
                    name=f"POST_TO_{io.metadata.identifier}<{medium.mid}>",
                )
