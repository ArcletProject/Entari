# Edoves
A new abstract framework based on Cesloi

## Example

main.py:
```python
from edoves.builtin.mah.module import MessageModule
from edoves.main import Edoves

app = Edoves(
    debug=True,
    profile={
        "verify_token": "INITKEYWylsVdbr",
        "port": "9090",
        "account": 3165388245
    }
)

app.activate_modules(MessageModule)
app.run()
```
edoves/builtin/mah/module.py:
```python
from typing import Type
from edoves.main.module import MediumModule
from ..medium import Message
from edoves.builtin.mah import VERIFY_CODE
from edoves.main.typings import TMProtocol
from ..types import MType


class MessageModule(MediumModule):
    medium_type = Type[Message]
    identifier = VERIFY_CODE

    def __init__(self, protocol: TMProtocol):
        super().__init__(protocol)

        @self.new_handler(MType.ALL)
        async def test1(msg: Message):
            return msg.content


@MessageModule.prefab_handler(MType.Friend)
def test(msg: Message):
    return msg.purveyor

```
