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
$ entari
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
  ~record_message: true
  ::auto_reload:
    watch_dirs: ["."]
  ::echo: true
  ::inspect: true
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
from arclet.entari import Session, Entari, WS, command

@command.on("add {a} {b}")
def add(a: int, b: int):
    return f"{a + b = }"


app = Entari(WS(port=5500, token="XXX"))
app.run()
```

编写插件:

```python
from arclet.entari import Session, MessageCreatedEvent, metadata

metadata(
    name="Hello, World!",
    author=["Arclet"],
    version="0.1.0",
    description="A simple plugin that replies 'Hello, World!' to every message."
)
# or __plugin_metadata__ = PluginMetadata(...)

@MessageCreatedEvent.dispatch()
async def _(session: Session):
    await session.send("Hello, World!")
```

加载插件:

```python
from arclet.entari import Entari, WS, load_plugin

app = Entari(WS(port=5140, path="satori"))
load_plugin("example_plugin")
load_plugin("::echo")
load_plugin("::auto_reload", {"watch_dirs": ["plugins"]})

app.run()
```

