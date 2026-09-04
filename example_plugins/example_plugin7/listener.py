from arclet.entari import BasicConfModel, MessageCreatedEvent, plugin


class Config(BasicConfModel):
    foo: str
    bar: str


plugin.metadata(__file__, config=Config)
conf = plugin.get_config(Config)


@plugin.listen(MessageCreatedEvent)
async def _():
    print(conf, 2)
