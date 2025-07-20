from dataclasses import field
from typing import Optional, Union

from arclet.entari import BasicConfModel, plugin
from arclet.entari.config import config_model_validate
from arclet.entari.event.config import ConfigReload

try:
    from graia.amnesia.builtins.sqla import SqlalchemyService
    from graia.amnesia.builtins.sqla.model import Base as Base
    from graia.amnesia.builtins.sqla.types import EngineOptions
    from sqlalchemy.engine.url import URL
except ImportError:
    raise ImportError("Please install `sqlalchemy` first. Install with `pip install arclet-entari[db]`") from None


class Config(BasicConfModel):
    type: str = "sqlite"
    """数据库类型，默认为 sqlite"""
    name: str = "data.db"
    """数据库名称/文件路径"""
    driver: str = "aiosqlite"
    """数据库驱动，默认为 aiosqlite；其他类型的数据库驱动参考 SQLAlchemy 文档"""
    host: Optional[str] = None
    """数据库主机地址。如果是 SQLite 数据库，此项可不填。"""
    port: Optional[int] = None
    """数据库端口号。如果是 SQLite 数据库，此项可不填。"""
    username: Optional[str] = None
    """数据库用户名。如果是 SQLite 数据库，此项可不填。"""
    password: Optional[str] = None
    """数据库密码。如果是 SQLite 数据库，此项可不填。"""
    query: dict[str, Union[list[str], str]] = field(default_factory=dict)
    """数据库连接参数，默认为空字典。可以传入如 `{"timeout": "30"}` 的参数。"""
    options: EngineOptions = field(default_factory=lambda: {"echo": None, "pool_pre_ping": True})

    @property
    def url(self) -> URL:
        if self.type == "sqlite":
            return URL.create(f"{self.type}+{self.driver}", database=self.name, query=self.query)
        return URL.create(
            f"{self.type}+{self.driver}", self.username, self.password, self.host, self.port, self.name, self.query
        )


plugin.metadata(
    "Database 服务",
    ["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    "0.1.0",
    description="基于 SQLAlchemy 的数据库服务插件",
    urls={
        "homepage": "https://github.com/ArcletProject/Entari/tree/main/arclet/entari/builtins/database.py",
    },
    config=Config,
)

_config = plugin.get_config(Config)

try:
    plugin.add_service(serv := SqlalchemyService(_config.url, _config.options))
except Exception as e:
    raise RuntimeError("Failed to initialize SqlalchemyService. Please check your database configuration.") from e


@plugin.listen(ConfigReload)
async def reload_config(event: ConfigReload):
    if event.scope != "plugin":
        return None
    if event.key not in ("::database", "arclet.entari.builtins.database"):
        return None
    new_conf = config_model_validate(Config, event.value)
    await serv.db.stop()
    serv.db = serv.db.__class__(new_conf.url, new_conf.options)
    await serv.db.initialize()
    serv.get_session = serv.db.session_factory

    async with serv.db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return True


BaseOrm = Base

__all__ = ["Base", "BaseOrm"]
