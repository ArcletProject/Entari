import json

from arclet.alconna import Alconna, Args, CommandMeta, Field, MultiVar, Option, Subcommand, store_true
from arclet.letoderea import Subscriber

from arclet.entari import Session, command, keeping, metadata, plugin
from arclet.entari.event.plugin import PluginLoadedSuccess
from arclet.entari.filter import admins, superusers
from arclet.entari.localdata import local_data
from arclet.entari.plugin import PluginRole, plugin_service

metadata(
    "插件控制器",
    PluginRole.UTILITY,
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="提供装饰器和工具函数以便于用户控制插件的可用性，比如在负载均衡，特定群下禁用插件等",
    config=None,
)

channel_plugin_disables_file = local_data.get_data_file("control", "plugin_disables.json")


def _save_data(data: dict):
    with channel_plugin_disables_file.open("w+", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


plugin_disables: dict[str, dict[str, bool]] = keeping("plugin_disables", obj_factory=dict, dispose=_save_data)

plugin_control = Alconna(
    "plugin",
    Subcommand("list", alias=["列出"]),
    Subcommand(
        "disable",
        Args["names", MultiVar(str), Field(completion=lambda: "试试用 help")],
        Option("--global", alias=["-g", "全局"], action=store_true, default=False, help_text="全局禁用"),
        alias=["ban", "禁用"],
        help_text="禁用插件",
    ),
    Subcommand(
        "enable",
        Args["names", MultiVar(str), Field(completion=lambda: "试试用 help")],
        Option("--global", alias=["-g", "全局"], action=store_true, default=False, help_text="全局禁用"),
        alias=["启用"],
        help_text="启用插件",
    ),
    Subcommand("clear", alias=["清空"], help_text="清空所有被禁用的插件"),
    meta=CommandMeta(
        "管理特定频道/群组下功能插件的启用状态",
        usage="可传入多个功能名, 以空格分隔",
        example="$插件 列出\n$插件 禁用 help",
    ),
)

plugin_ctl_disp = command.mount(plugin_control, skip_for_unmatch=False).as_execute()


plug = plugin.get_plugin()
superuser_check = superusers().check


@plug.dispatch(PluginLoadedSuccess)
async def hook(event: PluginLoadedSuccess):
    if event.plugin_id == plug.id:
        return

    target = plugin_service.plugins[event.plugin_id]
    plg_id = target.id
    while plg_id in plugin_service._subplugined:
        plg_id = plugin_service._subplugined[plg_id]

    async def _check_disable(session: Session, _: Subscriber):
        if not session.event.channel:
            return True
        ch_id = session.event.channel.id
        if ch_id not in plugin_disables:
            return True
        return not plugin_disables[ch_id].get(plg_id, False)

    plug.effect(lambda: target._hooks.append(_check_disable), "control_inject")


@plugin_ctl_disp.assign("$main")
async def _():
    return """\
插件管理
- 列出：列出所有已安装的功能插件
- 禁用：禁用插件
- 启用：启用插件
- 清空：清空所有被禁用的插件
"""


@plugin_ctl_disp.assign("list")
async def _(session: Session):
    plgs = plugin.get_plugins()
    res = "已安装的功能插件：\n"
    for plg in plgs:
        meta = plg.metadata
        if meta and meta.role is not PluginRole.NORMAL:
            continue
        line = f"- {meta.name}: {meta.description or '无描述'}" if meta else f"- {plg.id}"
        stat = "✅ 全局启用" if plg.is_available else "❌ 全局禁用"
        if session.event.channel and session.event.channel.id in plugin_disables:
            stat = "❌ 禁用" if plugin_disables[session.event.channel.id].get(plg.id, False) else "✅ 启用"
        res += f"{line} {stat}\n"
    return res


@plugin_ctl_disp.assign("disable")
@admins()
async def _(
    session: Session,
    names: tuple[str, ...],
    global_: command.Query[bool] = command.Query("disable.global.value", False),
):
    plgs = plugin.get_plugins()
    plgs = [plg for plg in plgs if not plg.metadata or plg.metadata.role is PluginRole.NORMAL]
    name_to_id = {plg.metadata.name: plg.id for plg in plgs if plg.metadata}
    ids = {plg.id for plg in plgs}
    for name in names:
        if name not in name_to_id and name not in ids:
            await session.send_message(f"未找到插件：{name}")
            continue
        plg_id = name_to_id.get(name, name)
        if global_.result:
            if await superuser_check(session):
                return "只有超级用户才能全局禁用插件"
            if await plugin.disable_plugin(plg_id):
                await session.send_message(f"已全局禁用插件：{name}")
            else:
                await session.send_message(f"未找到插件：{plg_id}")
        elif session.event.channel:
            ch_id = session.event.channel.id
            if ch_id not in plugin_disables:
                plugin_disables[ch_id] = {}
            plugin_disables[ch_id][plg_id] = True
            await session.send_message(f"已在当前频道禁用插件：{name}")


@plugin_ctl_disp.assign("enable")
@admins()
async def _(
    session: Session, names: tuple[str, ...], global_: command.Query[bool] = command.Query("enable.global.value", False)
):
    plgs = plugin.get_plugins()
    plgs = [plg for plg in plgs if not plg.metadata or plg.metadata.role is PluginRole.NORMAL]
    name_to_id = {plg.metadata.name: plg.id for plg in plgs if plg.metadata}
    ids = {plg.id for plg in plgs}
    for name in names:
        if name not in name_to_id and name not in ids:
            await session.send_message(f"未找到插件：{name}")
            continue
        plg_id = name_to_id.get(name, name)
        if global_.result:
            if await superuser_check(session):
                return "只有超级用户才能全局启用插件"
            if await plugin.enable_plugin(plg_id):
                await session.send_message(f"已全局启用插件：{name}")
            else:
                await session.send_message(f"未找到插件：{plg_id}")
        elif session.event.channel:
            ch_id = session.event.channel.id
            if ch_id in plugin_disables and plugin_disables[ch_id].get(plg_id, False):
                plugin_disables[ch_id][plg_id] = False
                await session.send_message(f"已在当前频道启用插件：{name}")


@plugin_ctl_disp.assign("clear")
@admins()
async def _(session: Session):
    if session.event.channel:
        ch_id = session.event.channel.id
        if ch_id in plugin_disables:
            del plugin_disables[ch_id]
            return "已清空当前频道的插件禁用列表"
        else:
            return "当前频道没有被禁用的插件"
