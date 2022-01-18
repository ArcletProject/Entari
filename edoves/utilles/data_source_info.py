from . import DataStructure
from .security import generate_identifier


class DataSourceInfo(DataStructure):
    platform: str
    name: str
    version: str

    def __init__(
            self,
            platform: str,
            name: str,
            version: str
    ):
        super().__init__(platform=platform, name=name, version=version)
        self.__identifier = generate_identifier(f"{self.platform}_{self.name}_{self.version}")

    @property
    def instance_identifier(self):
        return self.__identifier
