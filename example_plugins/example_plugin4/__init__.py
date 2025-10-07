from arclet.entari import metadata, load_plugin, listen
from arclet.entari.event.plugin import PluginLoadedSuccess

metadata(__file__, description="A test plugin 4")


load_plugin("example_plugin4.foo.bar")
