from typing import Type
from arclet.edoves.main.config import TemplateConfig
from arclet.edoves.main.utilles.security import MIRAI_API_HTTP_DEFAULT
from .protocol import MAHProtocol
from .server_docker import MAHServerDocker
from .parsers import *

VERIFY_CODE = MIRAI_API_HTTP_DEFAULT


class MAHConfig(TemplateConfig):
    protocol: Type[MAHProtocol] = MAHProtocol
    server_docker: Type[MAHServerDocker] = MAHServerDocker
    modules_base_path = "./edoves_modules/mah"
