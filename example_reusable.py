from arclet.entari import BasicConfModel, Session, filter_, use, plugin_config, metadata


class Config(BasicConfModel):
    input: str
    output: str


metadata(name="example_reusable", config=Config)


conf = plugin_config(Config)


@filter_(lambda sess: sess.content == conf.input)
@use("message-created")
async def _(sess: Session):
    await sess.send(conf.output)
