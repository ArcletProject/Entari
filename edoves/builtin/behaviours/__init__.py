import time

from ...main.monomer import MonomerController
from ...main.behaviour import BaseMonoBehaviour


class EdovesMainBehaviour(BaseMonoBehaviour):
    async def on_destroy(self):
        pass

    async def on_disable(self):
        pass

    async def on_enable(self):
        pass

    async def update(self):
        self.monomer.protocol.edoves.logger.info("this is update!")

    async def start(self):
        start_time = time.time()
        self.monomer.protocol.edoves.logger.info("Edoves Application Starting...")
        self.monomer.protocol.edoves.logger.info("this is start!")
        self.monomer.protocol.edoves.logger.info(f"Edoves Application Started with {time.time() - start_time:.2}s")

    async def activate(self):
        self.monomer.add_tags("bot", "Edoves", "app")
        self.monomer.protocol.edoves.monomer_controller = MonomerController(self.monomer.protocol.edoves)
        self.monomer.protocol.edoves.monomer_controller.add(self.monomer.identifier, self.monomer)
