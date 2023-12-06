# arclet-entari

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