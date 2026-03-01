from typing import Literal

from .models.default import BasicConfModel as BasicConfModel
from .models.default import field as model_field


class WebsocketsInfo(BasicConfModel):
    """Satori Server WebSocket Configuration"""

    type: Literal["websocket", "websockets", "ws"]
    host: str = model_field(default="localhost", description="WebSocket server host")
    port: int = model_field(default=5140, description="WebSocket server port")
    path: str = model_field(default="", description="WebSocket server endpoint path")
    secure: bool = model_field(default=False, description="Whether to use HTTPS and WSS for the server connection")
    token: str | None = model_field(default=None, description="Authentication token for the WebSocket server")
    timeout: float | None = model_field(default=None, description="Connection timeout in seconds")


class WebhookInfo(BasicConfModel):
    """Satori Server Webhook Configuration"""

    type: Literal["webhook", "wh", "http"]
    host: str = model_field(default="127.0.0.1", description="Webhook self-server host")
    port: int = model_field(default=8080, description="Webhook self-server port")
    path: str = model_field(default="v1/events", description="Webhook self-server endpoint path")
    secure: bool = model_field(default=False, description="Whether to use HTTPS for the server connection")
    token: str | None = model_field(default=None, description="Authentication token for the webhook")
    server_host: str = model_field(default="localhost", description="Target server host")
    server_port: int = model_field(default=5140, description="Target server port")
    server_path: str = model_field(default="", description="Target server endpoint path")
    timeout: float | None = model_field(default=None, description="Connection timeout in seconds")


class LogSaveInfo(BasicConfModel):
    """Configuration for saving logs to a file"""

    rotation: str = model_field(default="00:00", description="Log rotation time, e.g., '00:00' for daily rotation")
    compression: str | None = model_field(default=None, description="Compression format for log saving, e.g., 'zip'")
    colorize: bool = model_field(default=True, description="Whether to colorize the log output")


class LogInfo(BasicConfModel):
    """Configuration for the application logs"""

    level: int | str = model_field(default="INFO", description="Log level for the application")
    ignores: list[str] = model_field(default_factory=list, description="Log ignores for the application")
    save: LogSaveInfo | bool | None = model_field(
        default=None,
        description="Log saving configuration, if None or False, logs will not be saved",
    )
    rich_error: bool = model_field(default=False, description="Whether enable rich traceback for exceptions")
    short_level: bool = model_field(default=False, description="Whether use short log level names")


class BasicConfig(BasicConfModel):
    """Basic configuration for the Entari application"""

    network: list[WebsocketsInfo | WebhookInfo] = model_field(default_factory=list, description="Network configuration")
    ignore_self_message: bool = model_field(default=True, description="Whether ignore self-send message event")
    skip_req_missing: bool = model_field(
        default=False, description="Whether skip Event Handler if requirement is missing"
    )
    log: LogInfo = model_field(default_factory=LogInfo, description="Log configuration")
    log_level: int | str | None = model_field(default=None, description="[Deprecated] Log level for the application")
    log_ignores: list[str] | None = model_field(
        default=None, description="[Deprecated] Log ignores for the application"
    )
    prefix: list[str] = model_field(default_factory=list, description="Command prefix for the application")
    cmd_count: int = model_field(default=4096, description="Command count limit for the application")
    external_dirs: list[str] = model_field(default_factory=list, description="External directories to look for plugins")
    schema: bool = model_field(
        default=False, description="Whether generate JSON schema for the configuration (after application start)"
    )

    def __post_init__(self):
        if self.log_level is not None:
            self.log.level = self.log_level
        if self.log_ignores is not None:
            self.log.ignores = self.log_ignores
        if self.prefix.count(""):
            self.prefix = [p for p in self.prefix if p]
            self.prefix.append("")
