from arclet.entari import metadata, inject, listen
from arclet.entari.event.lifespan import Startup
from . import command

from example_plugin import kept_data

metadata(__file__)


@listen(Startup)
@inject({"id": "entari.plugin.auto_reload/watcher", "stage": "blocking"})  # type: ignore
async def startup():
    print(kept_data)


# from example_reusable import conf  # entari: plugin
