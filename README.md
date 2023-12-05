# arclet-entari

一个基于 `Satori` 协议的简易 IM framework

## 示例

```python
from arclet.entari import Channel, Entari, EntariCommands, Session, WebsocketsInfo

command = EntariCommands()


@command.on("add {a} {b}")
async def add(a: int, b: int, channel: Channel, session: Session):
    await session.send_message(channel, f"{a + b =}")


app = Entari()
app.apply(WebsocketsInfo(port=5500, token="XXX"))

app.run()
```