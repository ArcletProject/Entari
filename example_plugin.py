from arclet.entari import MessageCreatedEvent, Plugin, EntariCommands, ContextSession, AlconnaDispatcher, is_direct_message
from arclet.alconna import Alconna, Args, AllParam

plug = Plugin()

disp_message = plug.dispatch(MessageCreatedEvent)


@disp_message.on(auxiliaries=[is_direct_message])
async def _(event: MessageCreatedEvent):
    print(event.content)


on_alconna = plug.mount(AlconnaDispatcher(Alconna("chat", Args["content", AllParam])))


@on_alconna.on()
async def _(event: MessageCreatedEvent):
    print("matched:", event.content)


commands = EntariCommands.current()


@commands.on("add {a} {b}")
async def add(a: int, b: int, session: ContextSession):
    await session.send_message(f"{a + b =}")
