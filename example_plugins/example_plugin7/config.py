from arclet.entari.config import BasicConfModel, model_field


class Config(BasicConfModel):
    input: str
    output: str
    tools: dict[str, dict] = model_field(default_factory=dict)
