from typing import Dict
from edoves.data_source_info import DataSourceInfo
from edoves.main.protocol import NetworkProtocol


class MAHProtocol(NetworkProtocol):
    source_information = DataSourceInfo(
        platform="Tencent",
        name="mirai-api-http",
        version="default"
    )
    medium_type = Dict
