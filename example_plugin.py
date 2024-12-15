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
    scheduler,
    # Entari,
)
from arclet.entari.filter import Interval

metadata(__file__)

plug = Plugin.current()


@plug.use("::startup")
async def prepare():
    print("example: Preparing")


@plug.use("::cleanup")
async def cleanup():
    print("example: Cleanup")


@plug.dispatch(MessageCreatedEvent)
@Filter().public().bind
async def _(session: Session):
    if session.content == "test":
        resp = await session.send("This message will recall in 5s...")

        @scheduler.invoke(5)
        async def _():
            await session.message_delete(resp[0].id)

disp_message = plug.dispatch(MessageCreatedEvent)


@disp_message.on(auxiliaries=[Filter().public().to_me().and_(lambda sess: str(sess.content) == "aaa")])
async def _(session: Session):
    return await session.send("Filter: public message, to me, and content is 'aaa'")


@disp_message.on(auxiliaries=[Filter().public().to_me().not_(lambda sess: str(sess.content) == "aaa")])
async def _(session: Session):
    return await session.send("Filter: public message, to me, but content is not 'aaa'")


@command.on("add {a} {b}", [Interval(2, limit_prompt="太快了")])
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

# @scheduler.cron("* * * * *")
# async def broadcast(app: Entari):
#     for account in app.accounts.values():
#         channels = [channel for guild in (await account.guild_list()).data for channel in (await account.channel_list(guild.id)).data]
#         for channel in channels:
#             await account.send_message(channel, "Hello, World!")
