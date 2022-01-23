from typing import Type
from ...builtin.mah.protocol import MAHProtocol
from ...utilles.security import MIRAI_API_HTTP_DEFAULT
from ...main.config import TemplateConfig
from ...builtin.mah.server_docker import MAHServerDocker

VERIFY_CODE = MIRAI_API_HTTP_DEFAULT


class MAHConfig(TemplateConfig):
    protocol: Type[MAHProtocol] = MAHProtocol
    server_docker: Type[MAHServerDocker] = MAHServerDocker
