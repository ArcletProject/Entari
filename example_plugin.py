from arclet.entari import (
    Session,
    MessageChain,
    MessageCreatedEvent,
    Plugin,
    command,
    filter_,
    metadata,
    keeping,
    scheduler,
    local_data,
    # Entari,
)
from arclet.entari.event.command import CommandOutput
from arclet.entari.filter import Interval

metadata(__file__)

plug = Plugin.current()


@plug.use("::startup")
async def prepare():
    print(">> example: Preparing")


@plug.use("::cleanup")
async def cleanup():
    print(">> example: Cleanup")


@plug.dispatch(MessageCreatedEvent)
@filter_.public
async def _(session: Session):
    if session.content == "test":
        resp = await session.send("This message will recall in 5s...")

        @scheduler.invoke(5)
        async def _():
            await session.message_delete(resp[0].id)

disp_message = plug.dispatch(MessageCreatedEvent)


@disp_message.on()
@filter_.public & filter_.to_me & filter_(lambda sess: str(sess.content) == "aaa")
async def _(session: Session):
    return await session.send("Filter: public message, to me, and content is 'aaa'")


@disp_message
@filter_.public & filter_.to_me & filter_(lambda sess: str(sess.content) != "aaa")
async def _(session: Session):
    return await session.send("Filter: public message, to me, but content is not 'aaa'")


@command.on("add {a} {b}")
def add(a: int, b: int):
    return f"{a + b =}"


add.propagate(Interval(2, limit_prompt="太快了"))


kept_data = keeping("foo", [], lambda x: x.clear())


@command.on("append {data}")
def append(data: str):
    kept_data.append(data)
    return f"Appended {data}"


@command.on("show")
async def show(session: Session):
    res = await command.execute("echo 123")
    await session.send_message(f"Execute `echo 123` Result: {res}")
    return f"Data: {kept_data}"

TEST = 7

print([*Plugin.current()._scope.subscribers])
print(Plugin.current().subplugins)
print(local_data.get_temp_dir())
print(plug.config)


@plug.use("::before_send")
async def send_hook(message: MessageChain):
    return message + "喵"


@plug.use("::config/reload")
async def config_reload():
    print(">> Config Reloaded")
    return True


@plug.use("::plugin/loaded_success")
async def loaded_success(event):
    print(f">> Plugin {event.name} Loaded Successfully")


@plug.use("::plugin/unloaded")
async def unloaded(event):
    print(f">> Plugin {event.name} Unloaded")


@plug.dispatch(CommandOutput)
async def output_hook(event: CommandOutput):
    content = event.content
    return f"{event.type.title()}:\n{content}"

# @scheduler.cron("* * * * *")
# async def broadcast(app: Entari):
#     for account in app.accounts.values():
#         channels = [channel for guild in (await account.guild_list()).data for channel in (await account.channel_list(guild.id)).data]
#         for channel in channels:
#             await account.send_message(channel, "Hello, World!")
