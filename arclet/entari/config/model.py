from typing import Literal

from .models.default import BasicConfModel as BasicConfModel
from .models.default import field as model_field


class WebsocketsInfo(BasicConfModel):
    """Satori 服务器 WebSocket 配置"""

    type: Literal["websocket", "websockets", "ws"] = model_field(
        description="连接类型，必须是 'websocket'、'websockets' 或 'ws'"
    )
    host: str = model_field(default="localhost", description="服务器主机地址")
    port: int = model_field(default=5140, description="服务器端口")
    path: str = model_field(default="", description="服务器路径")
    secure: bool = model_field(default=False, description="是否使用安全连接（wss 和 https）")
    token: str | None = model_field(default=None, description="连接的鉴权令牌")
    timeout: float | None = model_field(default=None, description="连接超时时间（秒）")


class WebhookInfo(BasicConfModel):
    """Satori 服务器 Webhook 配置"""

    type: Literal["webhook", "wh", "http"] = model_field(description="连接类型，必须是 'webhook'、'wh' 或 'http'")
    host: str = model_field(default="127.0.0.1", description="本机 Webhook 服务器主机地址")
    port: int = model_field(default=8080, description="本机 Webhook 服务器端口")
    path: str = model_field(default="v1/events", description="本机 Webhook 服务器路径")
    secure: bool = model_field(default=False, description="是否使用安全连接（wss 和 https）")
    token: str | None = model_field(default=None, description="连接的鉴权令牌")
    server_host: str = model_field(default="localhost", description="发送请求的目标服务器主机地址")
    server_port: int = model_field(default=5140, description="发送请求的目标服务器端口")
    server_path: str = model_field(default="", description="发送请求的目标服务器路径")
    timeout: float | None = model_field(default=None, description="连接超时时间（秒）")


class LogSaveInfo(BasicConfModel):
    """日志保存相关配置"""

    rotation: str = model_field(
        default="00:00",
        description="日志轮转时间，支持时间字符串（如 '00:00' 表示每天午夜轮转）或文件大小（如 '10 MB'）",
    )
    compression: str | None = model_field(default=None, description="日志压缩格式，支持 'zip'、'tar'、'gz' 等常见格式")
    colorize: bool = model_field(default=True, description="是否在保存的日志中保留颜色信息")


class LogInfo(BasicConfModel):
    """日志相关配置"""

    level: int | str = model_field(default="INFO", description="日志级别")
    ignores: list[str] = model_field(
        default_factory=list, description="日志过滤器，指定要忽略的日志记录器名称列表（可以使用通配符）"
    )
    save: LogSaveInfo | bool | None = model_field(
        default=None,
        description="日志保存配置，设置为 False 或 None 则不保存日志",
    )
    rich_error: bool = model_field(default=False, description="是否使用 Rich 库美化错误日志")
    short_level: bool = model_field(default=False, description="是否在日志中使用简短的级别名称（如 'I' 代替 'INFO'）")


class BasicConfig(BasicConfModel):
    """Entari 应用的基础配置"""

    network: list[WebsocketsInfo | WebhookInfo] = model_field(default_factory=list, description="网络相关配置")
    ignore_self_message: bool = model_field(default=True, description="是否忽略自己发送的消息事件")
    skip_req_missing: bool = model_field(default=False, description="是否跳过无法执行的事件监听器")
    log: LogInfo = model_field(default_factory=LogInfo, description="日志相关配置")
    prefix: list[str] = model_field(default_factory=list, description="命令前缀列表，支持多个前缀（如 ['/', '!']）")
    nickname: str = model_field(default="", description="Bot 昵称，主要用于命令匹配")
    cmd_count: int = model_field(default=4096, description="命令数量限制，超过该数量的命令将无法注册")
    external_dirs: list[str] = model_field(default_factory=list, description="用来查找插件的外部目录列表，支持多个目录")
    schema: bool = model_field(default=False, description="是否为配置文件生成 JSON Schema（会在启动时生成）")
    check_metadata: bool = model_field(
        default=False, description="是否利用元数据进行插件导入检测（可能会增加启动时间）"
    )

    def __post_init__(self):
        if self.prefix.count(""):
            self.prefix = [p for p in self.prefix if p]
            self.prefix.append("")
