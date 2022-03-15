from arclet.alconna import Alconna, compile, Arpamar
from arclet.letoderea.utils import ArgumentPackage
from arclet.letoderea.entities.auxiliary import BaseAuxiliary
from ..main.message.chain import MessageChain


class AlconnaAuxiliary(BaseAuxiliary):
    alconna: Alconna

    def __init__(self, alconna: Alconna):
        self.analyser = compile(alconna)

        @self.set_aux("before_parse", "supply", keep=True)
        def supply(target_argument: ArgumentPackage) -> Arpamar:
            if target_argument.annotation == MessageChain:
                return self.analyser.analyse(target_argument.value)