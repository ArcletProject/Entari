from arclet.entari import MessageCreatedEvent, Plugin


plug = Plugin()

disp_message = plug.dispatch(MessageCreatedEvent)


@disp_message.on()
async def _(event: MessageCreatedEvent):
    print(event.content)
