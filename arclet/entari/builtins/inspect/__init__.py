from arclet.alconna import Alconna, Args, CommandMeta
from satori.element import At, Author, Sharp, select

from arclet.entari import MessageEvent, Session, command, metadata
from arclet.entari.command.model import Match

from .i18n import Lang

metadata(
    "inspect",
    ["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="Inspect on any user, group or channel",
)


inspect_cmd = Alconna(
    "inspect",
    Args["target?", [At, Sharp]],
    meta=CommandMeta(Lang.entari_plugin_inspect.description(), example="inspect @user\ninspect #channel\ninspect"),
)


SceneNames = {
    "DIRECT": Lang.entari_plugin_inspect.scene.direct,
    "TEXT": Lang.entari_plugin_inspect.scene.text,
    "VOICE": Lang.entari_plugin_inspect.scene.voice,
    "CATEGORY": Lang.entari_plugin_inspect.scene.category,
}


@command.on(inspect_cmd)
async def inspect(session: Session[MessageEvent], target: Match["At | Sharp"]):
    event = session.context
    texts = [
        Lang.entari_plugin_inspect.platform(platform=session.account.platform),
        Lang.entari_plugin_inspect.self(self_id=session.account.self_id),
        Lang.entari_plugin_inspect.scene.name(scene=SceneNames[session.channel.type.name]()),
        Lang.entari_plugin_inspect.guild(guild_id=event.guild.id if event.guild else None),
        Lang.entari_plugin_inspect.channel(channel_id=session.channel.id),
    ]
    if event.quote and (authors := select(event.quote, Author)):
        texts.append(Lang.entari_plugin_inspect.user(user_id=authors[0].id))
        await session.send_message("\n".join(texts))
        return
    if target.available:
        if isinstance(target.result, At) and target.result.id:
            await session.send_message(Lang.entari_plugin_inspect.user(user_id=target.result.id))
        elif isinstance(target.result, Sharp) and target.result.id:
            await session.send_message(Lang.entari_plugin_inspect.channel(channel_id=target.result.id))
        else:
            await session.send_message(Lang.entari_plugin_inspect.invalid())
        return
    texts.append(Lang.entari_plugin_inspect.user(user_id=session.user.id))
    await session.send_message("\n".join(texts))
    return
