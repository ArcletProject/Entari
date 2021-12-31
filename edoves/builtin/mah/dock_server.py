from edoves.main.dock_server import BaseDockServer
from edoves.security import MIRAI_API_HTTP_DEFAULT


class MAHDockServer(BaseDockServer):
    identifier = MIRAI_API_HTTP_DEFAULT
