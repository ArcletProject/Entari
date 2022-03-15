from typing import TYPE_CHECKING, Dict
from arclet.letoderea.utils import ContextModel


if TYPE_CHECKING:
    from . import Edoves
    from .scene import EdovesScene
    from .module import BaseModule
    from .monomer import Monomer
    from .event import EdovesBasicEvent

edoves_instance: "ContextModel[Edoves]" = ContextModel("edoves")
current_scene: "ContextModel[EdovesScene]" = ContextModel("current_scene")
ctx_module: "ContextModel[BaseModule]" = ContextModel("module")
ctx_monomer: "ContextModel[Monomer]" = ContextModel("purveyor")
ctx_event: "ContextModel[EdovesBasicEvent]" = ContextModel("event")


context_map: Dict[str, ContextModel] = {
    "Edoves": edoves_instance,
    "Scene": current_scene,
    "Event": ctx_event,
    "Module": ctx_module,
    "Monomer": ctx_monomer,
}