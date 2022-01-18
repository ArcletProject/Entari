# Edoves
A new abstract framework based on Cesloi

## Example

main.py:
```python
from arclet.edoves.builtin.mah.module import MessageModule
from arclet.edoves.builtin.client import AioHttpClient
from arclet.edoves.main import Edoves

app = Edoves(
    debug=True,
    profile={  # 默认为MAH的配置
        "verify_token": "INITKEYWylsVdbr",
        "port": "9090",
        "client": AioHttpClient,
        "account": 3165388245
    }
)

app.activate_modules(MessageModule)
app.run()
```
edoves/builtin/mah/module.py:
```python
from typing import Type
from arclet.edoves.main.module import MediumModule
from arclet.edoves.main.typings import TMProtocol
from arclet.edoves.builtin.mah import VERIFY_CODE
from arclet.edoves.builtin.mah.medium import Message
from arclet.edoves.builtin.mah.types import MType

async def test1(msg: Message):
    return msg.content

class MessageModule(MediumModule):
    medium_type = Type[Message]
    identifier = VERIFY_CODE

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)
        self.new_handler(MType.ALL, test1)
        


def test(msg: Message):
    return msg.purveyor
MessageModule.new_handler(MType.Friend, test)
```
