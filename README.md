# Edoves
A new abstract framework based on Cesloi

## Example

main.py:
```python
from arclet.edoves.builtin.mah.messages import Source
from arclet.edoves.builtin.mah.module import MessageModule
from arclet.edoves.builtin.commander import Commander
from arclet.edoves.builtin.medium import Message
from arclet.edoves.builtin.event.message import AllMessage
from arclet.edoves.main import Edoves, Monomer
from arclet.edoves.builtin.client import AioHttpClient

app = Edoves(
    debug=False,
    profile={
        "verify_token": "INITKEYWylsVdbr",
        "port": "9080",
        "client": AioHttpClient,
        "account": 3542928737
    }
)
message_module = app.scene.activate_module(MessageModule)
commander = app.scene.activate_module(Commander)    


@commander.command("print <content:str>")
async def _(content: str, message: Message, sender: Monomer, bot: Edoves):
    await message.set("This is commander test").send()
    await message.set(f"I received content:{content} from {sender.metadata.name}").send()
    if content == "all_group":
        await message.set(f"{[k.metadata.name for k in bot.self.filter_parents('Group')]}").send()
    if content == "friend":
        await message.set(f"{[k.metadata.name for k in bot.self.filter_children('Friend')]}").send()


async def test_message_reaction(message: Message):
    if message.content.startswith("Hello"):
        await message.purveyor.action("send_with")(
            message, reply=True, quote=message.content.find(Source).id, type=message.type)
        await message.set("I received 'Hello World!'").send()


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
