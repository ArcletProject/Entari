from arclet.entari import metadata, inject, listen, requires
from arclet.entari.event.lifespan import Startup
from . import command

from example_plugin import kept_data

metadata(__file__)
#requires("example_plugin")


@listen(Startup)
@inject({"id": "entari.plugin.auto_reload/watcher", "stage": "blocking"})
async def startup():
    print(111111111111111111111111111111111111111111)


# from example_reusable import conf  # entari: plugin
