from arclet.entari import metadata
from .config import Config
from . import foo as foo

metadata(__file__, description="A test plugin 6", config=Config)
