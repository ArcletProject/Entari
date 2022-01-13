from edoves.main.server_docker import BaseServerDocker
from edoves.security import MIRAI_API_HTTP_DEFAULT


class MAHServerDocker(BaseServerDocker):
    identifier = MIRAI_API_HTTP_DEFAULT
