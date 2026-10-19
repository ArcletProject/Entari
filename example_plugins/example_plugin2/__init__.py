from typing import Annotated

from arclet.entari import metadata, listen
from arclet.entari.event.lifespan import Startup
from . import command

from arclet.entari.builtins.auto_reload import Watcher
from arclet.entari.core import on_stage

metadata(__file__)


@listen(Startup)
async def startup1(_: Watcher):
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>> startup1 <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
    print("waiting for watcher to be prepared...")


@listen(Startup)
async def startup2(_: Annotated[Watcher, on_stage("blocking")]):
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>> startup2 <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
    print("waiting for watcher to be blocking...")


@listen(Startup)
async def startup3(_: Watcher = on_stage("prepared")):
    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>> startup3 <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
    print("waiting for watcher to be prepared...")


# from example_reusable import conf  # entari: plugin
