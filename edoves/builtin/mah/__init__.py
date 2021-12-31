from typing import Type
from edoves.builtin.mah.protocol import MAHProtocol
from ...security import MIRAI_API_HTTP_DEFAULT
from ...main.config import TemplateConfig
from edoves.builtin.mah.dock_server import MAHDockServer

VERIFY_CODE = MIRAI_API_HTTP_DEFAULT


class MAHConfig(TemplateConfig):
    protocol: Type[MAHProtocol] = MAHProtocol
    dock_server: Type[MAHDockServer] = MAHDockServer
