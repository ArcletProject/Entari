# Edoves
A new abstract framework based on Cesloi

## Example

main.py:
```python
from arclet.edoves.builtin.mah.module import MessageModule
from arclet.edoves.builtin.medium import Message
from arclet.edoves.builtin.event.message import AllMessage
from arclet.edoves.main import Edoves
from arclet.edoves.builtin.client import AioHttpClient

app = Edoves(
    debug=False,
    profile={
        "verify_token": "INITKEYWylsVdbr",
        "port": "9090",
        "client": AioHttpClient,
        "account": 3165388245
    }
)
message_module = app.scene.activate_module(MessageModule)
message_module.set_parent(app.self)


async def test_message_reaction(message: Message):
    if message.content.startswith("Hello"):
        print("I received 'Hello World!'")

message_module.new_handler(AllMessage, test_message_reaction)
app.run()
```
edoves/builtin/mah/module.py:
```python
from arclet.edoves.main.module import BaseModule, ModuleMetaComponent
from arclet.edoves.builtin.mah import VERIFY_CODE


class MessageModuleData(ModuleMetaComponent):
    identifier = VERIFY_CODE


class MessageModule(BaseModule):
    prefab_metadata = MessageModuleData


```
