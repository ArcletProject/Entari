import re
import sys
from arclet.entari import (
    Session,
    MessageChain,
    MessageCreatedEvent,
    Plugin,
    Filter,
    command,
    metadata,
    keeping,
)

metadata(__file__)

plug = Plugin.current()


@plug.use("::startup")
async def prepare():
    print("example: Preparing")


@plug.use("::cleanup")
async def cleanup():
    print("example: Cleanup")


disp_message = MessageCreatedEvent.dispatch()


@disp_message
@Filter().public.bind
async def _(msg: MessageChain, session: Session):
    content = msg.extract_plain_text()
    if re.match(r"(.{0,3})(上传|设定)(.{0,3})(上传|设定)(.{0,3})", content):
        return await session.send("上传设定的帮助是...")


disp_message1 = plug.dispatch(MessageCreatedEvent)


@disp_message1.on(auxiliaries=[Filter().public.to_me.and_(lambda sess: str(sess.content) == "aaa")])
async def _(session: Session):
    return await session.send("Filter: public message, to me, and content is 'aaa'")


@disp_message1.on(auxiliaries=[Filter().public.to_me.not_(lambda sess: str(sess.content) == "aaa")])
async def _(session: Session):
    return await session.send("Filter: public message, to me, but content is not 'aaa'")


@command.on("add {a} {b}")
def add(a: int, b: int):
    return f"{a + b =}"


kept_data = keeping("foo", [], lambda x: x.clear())


@command.on("append {data}")
def append(data: str):
    kept_data.append(data)
    return f"Appended {data}"


@command.on("show")
async def show(session: Session):
    res = await command.execute("echo 123")
    await session.send_message(f"Echo Result: {res}")
    return f"Data: {kept_data}"

TEST = 5

print([*Plugin.current().dispatchers.keys()])
print(Plugin.current().subplugins)
print("example_plugin not in sys.modules (expect True):", "example_plugin" not in sys.modules)


@plug.use("::before_send")
async def send_hook(message: MessageChain):
    return message + "喵"
