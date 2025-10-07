from arclet.entari import metadata, command

from ..tools.qux import calc


metadata(__file__, description="A test plugin 5")


@command.on("exam5 <x> <y>")
def exam5(x: int, y: int):
    return f"example_plugin5: {x} * {y} = {calc(x, y)}"
