from arclet.entari import BasicConfModel, Session, filter_, MessageCreatedEvent, listen, plugin_config


class Config(BasicConfModel):
    input: str
    output: str


conf = plugin_config(Config)


@filter_(lambda sess: sess.content == conf.input)
@listen(MessageCreatedEvent)
async def _(sess: Session):
    await sess.send(conf.output)
