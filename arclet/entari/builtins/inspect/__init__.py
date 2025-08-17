from arclet.alconna import Alconna, Args, CommandMeta
from satori.element import At, Author, Sharp, select

from arclet.entari import MessageEvent, Session, command, metadata
from arclet.entari.command.model import Match

from .i18n import Lang

metadata(
    "inspect",
    [{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="Inspect on any user, group or channel",
)


inspect_cmd = Alconna(
    "inspect",
    Args["target?", [At, Sharp]],
    meta=CommandMeta(Lang.entari_plugin_inspect.description.cast(), example="inspect @user\ninspect #channel\ninspect"),
)


SceneNames = {
    "DIRECT": Lang.entari_plugin_inspect.scene.direct,
    "TEXT": Lang.entari_plugin_inspect.scene.text,
    "VOICE": Lang.entari_plugin_inspect.scene.voice,
    "CATEGORY": Lang.entari_plugin_inspect.scene.category,
}
TP = "{platform}\n{self}\n{scene}\n{guild}\n{channel}\n{user}"


@command.on(inspect_cmd)
async def inspect(session: Session[MessageEvent], target: Match["At | Sharp"]):
    event = session.event
    texts = {
        "platform": Lang.entari_plugin_inspect.platform(platform=session.account.platform),
        "self": Lang.entari_plugin_inspect.self(self_id=session.account.self_id),
        "scene": Lang.entari_plugin_inspect.scene.name(scene=SceneNames[session.channel.type.name]()),
        "guild": Lang.entari_plugin_inspect.guild(guild_id=event.guild.id if event.guild else None),
        "channel": Lang.entari_plugin_inspect.channel(channel_id=session.channel.id),
    }
    if target.available:
        if isinstance(target.result, At) and target.result.id:
            texts["user"] = Lang.entari_plugin_inspect.user(user_id=target.result.id)
        elif isinstance(target.result, Sharp) and target.result.id:
            texts["channel"] = Lang.entari_plugin_inspect.channel(channel_id=target.result.id)
        else:
            await session.send_message(Lang.entari_plugin_inspect.invalid())
            return
    if "user" not in texts:
        if event.quote and (authors := select(event.quote, Author)):
            texts["user"] = Lang.entari_plugin_inspect.user(user_id=authors[0].id)
        else:
            texts["user"] = Lang.entari_plugin_inspect.user(user_id=session.user.id)

    await session.send_message(TP.format(**texts))
    return
