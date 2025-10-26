from arclet.entari import BasicConfModel, plugin_config


class Config(BasicConfModel):
    a: int = 123
    b: str = "example_plugin6"


config = plugin_config(Config)
