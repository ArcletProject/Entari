from typing import Dict, Union

from ..medium import Message
from ...message.chain import MessageChain
from ...utilles.data_source_info import DataSourceInfo
from ...main.medium import BaseMedium
from ...main.protocol import NetworkProtocol, TM
from ...main.typings import TData


class MAHProtocol(NetworkProtocol):
    async def transform_medium(self, medium: BaseMedium) -> Union[TM, TData]:
        pass

    async def parse_raw_data(self, data: TData) -> BaseMedium:
        pass

    async def test_set_message(self):
        self.scene.module_protocol.set_medium(
            Message.create(self.scene.edoves.self, MessageChain, "Message")(MessageChain.create("Hello,World!"))
        )
        await self.scene.module_protocol.broadcast_medium("AllMessage", Message)

    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="default"
    )
    medium_type = Dict
