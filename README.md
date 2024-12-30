<div align="center"> 
  
# Entari

  > _lí no etheclim, nann ze entám rish._
  
</div>

[![Licence](https://img.shields.io/github/license/ArcletProject/Entari)](https://github.com/ArcletProject/Entari/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-entari)](https://pypi.org/project/arclet-entari)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-entari)](https://www.python.org/)
![Entari](https://img.shields.io/badge/Arclet-Entari-2564c2.svg)

一个基于 `Satori` 协议的简易 IM framework

## 示例

使用命令行:
```shell
# 生成配置文件
$ entari new
```
```shell
# 运行
$ entari run
```

使用配置文件:
```yaml
# config.yml
basic:
  network:
    - type: ws
      host: "127.0.0.1"
      port: 5140
      path: "satori"
  ignore_self_message: true
  log_level: INFO
  prefix: ["/"]
plugins:
  $prelude:
    - ::auto_reload
  .record_message: {}
  ::auto_reload:
    watch_dirs: ["."]
  ::echo: {}
  ::inspect: {}
```

```python
from arclet.entari import Entari

app = Entari.load("config.yml")
app.run()
```


复读:

```python
from arclet.entari import Session, Entari, WS

app = Entari(WS(host="127.0.0.1", port=5140, path="satori"))

@app.on_message()
async def repeat(session: Session):
    await session.send(session.content)


app.run()
```

指令 `add {a} {b}`:

```python
from arclet.entari import Entari, WS, command

@command.on("add {a} {b}")
def add(a: int, b: int):
    return f"{a + b = }"


app = Entari(WS(port=5500, token="XXX"))
app.run()
```

编写插件:

```python
from arclet.entari import BasicConfModel, Session, MessageCreatedEvent, plugin


class Config(BasicConfModel):
    name: str


plugin.metadata(
    name="Hello, World!",
    author=["Arclet"],
    version="0.1.0",
    description="A simple plugin that replies 'Hello, World!' to every message.",
    config=Config
)
# or __plugin_metadata__ = PluginMetadata(...)

config = plugin.get_config(Config)

@plugin.listen(MessageCreatedEvent)  # or plugin.dispatch(MessageCreatedEvent)
async def _(session: Session):
    await session.send(f"Hello, World! {config.name}")
```

加载插件:

```python
from arclet.entari import Entari, WS, load_plugin

app = Entari(WS(port=5140, path="satori"))
load_plugin("example_plugin", {"name": "Entari"})
load_plugin("::echo")
load_plugin("::auto_reload", {"watch_dirs": ["plugins"]})

app.run()
```


## 配置文件

```yaml
basic:
  network:
    - type: ws
      host: "127.0.0.1"
      port: 5140
      path: "satori"
  ignore_self_message: true
  log_level: INFO
  prefix: ["/"]
plugins:
  $files: ["./plugins"]
  $prelude: ["::auto_reload"]
  .record_message:
    record_send: true
  .commands:
    use_config_prefix: false
  ::auto_reload:
    watch_dirs: ["."]
    watch_config: false
  ::echo: {}
  ::help:
    page_size: null
```

- `basic`: Entari 基础配置
  - `network`: 网络配置, 可写多个网络配置
    - `type`: 网络类型, 可填项有 `ws`, `websocket`, `wh`, `webhook`
    - `host`: satori 服务器地址
    - `port`: satori 服务器端口
    - `path`: satori 服务器路径
  - `ignore_self_message`: 是否忽略自己发送的消息事件
  - `log_level`: 日志等级
  - `prefix`: 指令前缀, 可留空
- `plugins`: 插件配置
  - `$files`: 额外的插件配置文件搜索目录
  - `$prelude`: 预加载插件列表
  - `.record_message`: 消息日志并配置
    - `record_send`: 是否记录发送消息 (默认为 `true`)
  - `.commands`: 指令插件配置 (适用于所有使用了 `command.on/command.command` 的插件)
    - `need_notice_me`: 指令是否需要 @ 机器人
    - `need_reply_me`: 指令是否需要回复机器人
    - `use_config_prefix`: 是否使用配置文件中的前缀
  - `::auto_reload`: 启用自动重载插件并配置
    - `watch_dirs`: 监听目录
    - `watch_config`: 是否监听配置文件的变化 (默认为 `true`)
  - `::echo`: 启用回声插件
  - `::help`: 启用帮助插件并配置
    - `help_command`: 帮助指令, 默认为 `help`
    - `help_alias`: 帮助指令别名, 默认为 `["帮助", "命令帮助"]`
    - `page_size`: 每页显示的指令数量, 留空则不分页

对于其他插件的配置, 有三种写法:

1. `foo.bar: {}` (仅启用插件)
2. `~foo.bar: xxxx` (禁用插件)
3. `foo.bar: {"key": "value"}` (启用插件并配置)
