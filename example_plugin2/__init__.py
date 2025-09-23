from arclet.entari import metadata, inject, listen
from arclet.entari.event.lifespan import Startup
from . import command

metadata(__file__)


@listen(Startup)
@inject({"id": "entari.plugin.auto_reload/watcher", "stage": "blocking"})
async def startup():
    print(111111111111111111111111111111111111111111)

# from example_plugin import kept_data  # entari: plugin
# from example_reusable import conf  # entari: plugin
