from typing import Dict
from ...utilles.data_source_info import DataSourceInfo
from ...main.medium import BaseMedium
from ...main.protocol import NetworkProtocol
from ...main.typings import TData


class MAHProtocol(NetworkProtocol):
    async def parse_raw_data(self, data: TData) -> BaseMedium:
        pass

    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="default"
    )
    medium_type = Dict
