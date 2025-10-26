from arclet.entari import command
from .utils import generate_token


@command.on("exam6")
def exam6():
    return f"example_plugin6 token: {generate_token()}"

