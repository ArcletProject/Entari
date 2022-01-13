from typing import Dict
from edoves.data_source_info import DataSourceInfo
from edoves.main.medium import BaseMedium
from edoves.main.protocol import NetworkProtocol
from edoves.main.typings import TData


class MAHProtocol(NetworkProtocol):
    async def parse_raw_data(self, data: TData) -> BaseMedium:
        pass

    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="default"
    )
    medium_type = Dict
