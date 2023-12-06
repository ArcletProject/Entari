<div align="center"> 
  
# Entari

  > _lo su etheclim, ti zo entaem rish._
  
</div>

[![Licence](https://img.shields.io/github/license/ArcletProject/Entari)](https://github.com/ArcletProject/Entari/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-entari)](https://pypi.org/project/arclet-entari)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-entari)](https://www.python.org/)
![Entari](https://img.shields.io/badge/Arclet-Entari-2564c2.svg)

一个基于 `Satori` 协议的简易 IM framework

## 示例

```python
from arclet.entari import ContextSession, Entari, EntariCommands, WebsocketsInfo

command = EntariCommands()


@command.on("add {a} {b}")
async def add(a: int, b: int, session: ContextSession):
    await session.send_message(f"{a + b =}")


app = Entari()
app.apply(WebsocketsInfo(port=5500, token="XXX"))

app.run()

```