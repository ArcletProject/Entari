import json

from arclet.alconna import Alconna, Args, CommandMeta, Field, MultiVar, Option, Subcommand, store_true
from arclet.letoderea import STOP

from arclet.entari import Session, command, keeping, metadata, plugin
from arclet.entari.command.provider import AlconnaSuppiler
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


def _load_data() -> dict:
    if channel_plugin_disables_file.exists():
        with channel_plugin_disables_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_data(data: dict):
    with channel_plugin_disables_file.open("w+", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


plugin_disables: dict[str, dict[str, dict[str, bool]]] = keeping(
    "plugin_disables", obj_factory=_load_data, dispose=_save_data
)
plugin_functions: dict[str, dict[str, str]] = keeping("plugin_functions", obj_factory=dict)

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
function_control = Alconna(
    "function",
    Subcommand("list", alias=["列出"]),
    Subcommand(
        "disable",
        Args["names", MultiVar(str), Field(completion=lambda: "试试用 help")],
        alias=["ban", "禁用"],
        help_text="禁用功能",
    ),
    Subcommand(
        "enable",
        Args["names", MultiVar(str), Field(completion=lambda: "试试用 help")],
        alias=["启用"],
        help_text="启用功能",
    ),
    Subcommand("clear", alias=["清空"], help_text="清空所有被禁用的功能"),
    meta=CommandMeta(
        "管理特定频道/群组下插件中功能的启用状态",
        usage="可传入多个功能名, 以空格分隔",
        example="$功能 列出\n$功能 禁用 Echo.echo",
    ),
)

plugin_ctl_disp = command.mount(plugin_control, skip_for_unmatch=False).as_execute()
function_ctl_disp = command.mount(function_control, skip_for_unmatch=False).as_execute()


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

    subscribers = plugin.get_plugin_subscribers(target)
    functions = {}
    sub_functino_map = {}
    for sub in subscribers:
        try:
            sup = sub.get_propagator(AlconnaSuppiler)
            sub_functino_map[sub.id] = sup.cmd.command
            functions.setdefault(sup.cmd.command, sup.cmd.meta.description)
        except ValueError:
            sub_functino_map[sub.id] = sub.__name__  # sub.label
            functions[sub.__name__] = sub.__doc__ or ""  # sub.label

    plugin_functions[plg_id] = functions

    def _check_disable(sub_id: str):

        async def _(session: Session | None = None):
            if not session:
                return
            if not session.event.channel:
                return
            ch_id = session.event.channel.id
            if ch_id not in plugin_disables:
                return
            disables = plugin_disables[ch_id].get(plg_id, {})
            if disables.get("$plugin", False):
                return STOP
            if disables.get(sub_functino_map[sub_id], False):
                print(sub_id, sub_functino_map[sub_id])
                return STOP

        return _

    def collect():
        for sub in subscribers:
            yield sub.propagate(_check_disable(sub.id), prepend=True)

    plug.effect(collect, "control_inject")


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
            stat = (
                "❌ 禁用"
                if plugin_disables[session.event.channel.id].get(plg.id, {}).get("$plugin", False)
                else "✅ 启用"
            )
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
            if plg_id not in plugin_disables[ch_id]:
                plugin_disables[ch_id][plg_id] = {}
            plugin_disables[ch_id][plg_id]["$plugin"] = True
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
            if ch_id in plugin_disables and plg_id in plugin_disables[ch_id]:
                plugin_disables[ch_id][plg_id]["$plugin"] = False
                await session.send_message(f"已在当前频道启用插件：{name}")


@plugin_ctl_disp.assign("clear")
@admins()
async def _(session: Session):
    if session.event.channel:
        ch_id = session.event.channel.id
        if ch_id in plugin_disables:
            for disables in plugin_disables[ch_id].values():
                disables["$plugin"] = False
            return "已清空当前频道的插件禁用列表"
        else:
            return "当前频道没有被禁用的插件"


@function_ctl_disp.assign("$main")
async def _():
    return """\
功能管理
- 列出：列出所有已安装的功能插件下的功能
- 禁用：禁用功能
- 启用：启用功能
- 清空：清空所有被禁用的功能
"""


@function_ctl_disp.assign("list")
async def _(session: Session):
    plgs = plugin.get_plugins()
    res = "已安装的功能插件及其功能：\n"
    for plg in plgs:
        meta = plg.metadata
        if meta and meta.role is not PluginRole.NORMAL:
            continue
        res += f"- {meta.name}: {meta.description or '无描述'}\n" if meta else f"- {plg.id}\n"
        functions = plugin_functions.get(plg.id, {})
        for func_name, func_desc in functions.items():
            stat = "✅ 启用" if plg.is_available else "❌ 插件禁用"
            if session.event.channel and session.event.channel.id in plugin_disables:
                disables = plugin_disables[session.event.channel.id].get(plg.id, {})
                if disables.get("$plugin", False):
                    stat = "❌ 插件禁用"
                elif disables.get(func_name, False):
                    stat = "❌ 禁用"
                else:
                    stat = "✅ 启用"
            res += f"  - {func_name}: {func_desc or '无描述'} {stat}\n"
    return res


@function_ctl_disp.assign("disable")
@admins()
async def _(
    session: Session,
    names: tuple[str, ...],
):
    plgs = plugin.get_plugins()
    plgs = [plg for plg in plgs if not plg.metadata or plg.metadata.role is PluginRole.NORMAL]
    name_to_id = {plg.metadata.name: plg.id for plg in plgs if plg.metadata}
    ids = {plg.id for plg in plgs}
    for name in names:
        target, func_name = name.split(".", 1) if "." in name else (None, name)
        if target:
            if target not in name_to_id and target not in ids:
                await session.send_message(f"未找到插件：{target}")
                continue
            plg_id = name_to_id.get(target, target)
        else:
            for plg in plgs:
                if func_name in plugin_functions.get(plg.id, {}):
                    plg_id = plg.id
                    break
            else:
                await session.send_message(f"未找到功能：{func_name}")
                continue
        if session.event.channel:
            ch_id = session.event.channel.id
            if ch_id not in plugin_disables:
                plugin_disables[ch_id] = {}
            if plg_id not in plugin_disables[ch_id]:
                plugin_disables[ch_id][plg_id] = {}
            plugin_disables[ch_id][plg_id][func_name] = True
            await session.send_message(f"已在当前频道禁用功能：{name}")


@function_ctl_disp.assign("enable")
@admins()
async def _(
    session: Session,
    names: tuple[str, ...],
):
    plgs = plugin.get_plugins()
    plgs = [plg for plg in plgs if not plg.metadata or plg.metadata.role is PluginRole.NORMAL]
    name_to_id = {plg.metadata.name: plg.id for plg in plgs if plg.metadata}
    ids = {plg.id for plg in plgs}
    for name in names:
        target, func_name = name.split(".", 1) if "." in name else (None, name)
        if target:
            if target not in name_to_id and target not in ids:
                await session.send_message(f"未找到插件：{target}")
                continue
            plg_id = name_to_id.get(target, target)
        else:
            for plg in plgs:
                if func_name in plugin_functions.get(plg.id, {}):
                    plg_id = plg.id
                    break
            else:
                await session.send_message(f"未找到功能：{func_name}")
                continue
        if session.event.channel:
            ch_id = session.event.channel.id
            if ch_id in plugin_disables and plg_id in plugin_disables[ch_id]:
                plugin_disables[ch_id][plg_id][func_name] = False
                await session.send_message(f"已在当前频道启用功能：{name}")


@function_ctl_disp.assign("clear")
@admins()
async def _(session: Session):
    if session.event.channel:
        ch_id = session.event.channel.id
        if ch_id in plugin_disables:
            for plg_id, disables in plugin_disables[ch_id].items():
                plugin_disables[ch_id][plg_id] = {"$plugin": disables.get("$plugin", False)}
            return "已清空当前频道的功能禁用列表"
        else:
            return "当前频道没有被禁用的功能"
