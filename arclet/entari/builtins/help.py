from dataclasses import field
import random
from typing import Optional

from arclet.alconna import (
    Alconna,
    Args,
    Arparma,
    CommandMeta,
    Field,
    Option,
    Subcommand,
    SubcommandResult,
    command_manager,
    namespace,
    store_true,
)
from tarina import lang

from arclet.entari import BasicConfModel, Session, command, metadata, plugin_config


class Config(BasicConfModel):
    help_command: str = "help"
    help_alias: list[str] = field(default_factory=lambda: ["帮助", "命令帮助"])
    help_all_alias: list[str] = field(default_factory=lambda: ["所有帮助", "所有命令帮助"])
    page_size: Optional[int] = None


config = plugin_config(Config)


metadata(
    "help",
    ["RF-Tar-Railt <rf_tar_railt@qq.com>"],
    description="展示所有命令帮助",
    config=Config,
)


with namespace("builtin/help") as ns:
    ns.disable_builtin_options = {"shortcut"}

    help_cmd = Alconna(
        config.help_command,
        Args[
            "query#选择某条命令的id或者名称查看具体帮助;/?",
            str,
            Field(
                "-1",
                completion=lambda: f"试试 {random.randint(0, len(command_manager.get_commands()))}",
                unmatch_tips=lambda x: f"预期输入为某个命令的id或者名称，而不是 {x}\n例如：/帮助 0",
            ),
        ],
        Option(
            "--page",
            Args["index", int],
            help_text="查看指定页数的命令帮助",
        ),
        Subcommand(
            "--namespace",
            Args["target?;#指定的命名空间", str],
            Option("--list", help_text="列出所有命名空间", action=store_true, default=False),
            alias=["-N", "命名空间"],
            help_text="是否列出命令所属命名空间",
        ),
        Option("--hide", alias=["-H", "隐藏"], help_text="是否列出隐藏命令", action=store_true, default=False),
        meta=CommandMeta(
            description="显示所有命令帮助",
            usage="可以使用 --hide 参数来显示隐藏命令，使用 -P 参数来显示命令所属插件名称",
            example=f"${config.help_command} 1",
        ),
    )

    for alias in set(config.help_alias):
        help_cmd.shortcut(alias, {"prefix": True, "fuzzy": False})
    for alias in set(config.help_all_alias):
        help_cmd.shortcut(alias, {"args": ["--hide"], "prefix": True, "fuzzy": False})


def help_cmd_handle(arp: Arparma, interactive: bool = False):
    is_namespace = arp.query[SubcommandResult]("namespace")
    page = arp.query[int]("page.index", 1)
    target_namespace = is_namespace.args.get("target") if is_namespace else None
    cmds = [
        i
        for i in command_manager.get_commands(target_namespace or "")
        if not i.meta.hide or arp.query[bool]("hide.value", False)
    ]
    if is_namespace and is_namespace.options["list"].value and not target_namespace:
        namespaces = {i.namespace: 0 for i in cmds}
        return "\n".join(
            f" 【{str(index).rjust(len(str(len(namespaces))), '0')}】{n}" for index, n in enumerate(namespaces.keys())
        )

    help_names = set()
    for i in cmds:
        help_names.update(i.namespace_config.builtin_option_name["help"])

    footer = lang.require("manager", "help_footer").format(help="|".join(sorted(help_names, key=lambda x: len(x))))
    show_namespace = is_namespace and not is_namespace.options["list"].value and not target_namespace
    if (query := arp.all_matched_args["query"]) != "-1":
        if query.isdigit():
            index = int(query)
            if index < 0 or index >= len(cmds):
                return "查询失败！"
            slot = cmds[index]
        elif not (slot := next((i for i in cmds if query == i.command), None)):
            command_string = "\n".join(
                (
                    f"【{str(index).rjust(len(str(len(cmds))), '0')}】"
                    f"{f'{slot.namespace}::' if show_namespace else ''}{slot.header_display} : "
                    f"{slot.meta.description}"
                )
                for index, slot in enumerate(cmds)
                if query in str(slot.command)
            )
            if not command_string:
                return "查询失败！"
            return f"{command_string}\n{footer}"
        return slot.get_help()

    if not config.page_size:
        header = lang.require("manager", "help_header")
        command_string = "\n".join(
            (
                f" 【{str(index).rjust(len(str(len(cmds))), '0')}】"
                f"{f'{slot.namespace}::' if show_namespace else ''}{slot.header_display} : "
                f"{slot.meta.description}"
            )
            for index, slot in enumerate(cmds)
        )
        return f"{header}\n{command_string}\n{footer}"

    max_page = len(cmds) // config.page_size + 1
    if page < 1 or page > max_page:
        page = 1
    max_length = config.page_size
    if interactive:
        footer += "\n" + "输入 '<', 'a' 或 '>', 'd' 来翻页"

    def _(_page: int):
        header = (
            lang.require("manager", "help_header")
            + "\t"
            + lang.require("manager", "help_pages").format(current=_page, total=max_page)
        )
        command_string = "\n".join(
            (
                f" 【{str(index).rjust(len(str(_page * max_length)), '0')}】"
                f"{f'{slot.namespace}::' if show_namespace else ''}{slot.header_display} : "
                f"{slot.meta.description}"
            )
            for index, slot in enumerate(
                cmds[(_page - 1) * max_length : _page * max_length], start=(_page - 1) * max_length
            )
        )
        return f"{header}\n{command_string}\n{footer}"

    if not interactive:
        return _(page)

    def generator(_page: int):
        while True:
            resp = yield _(_page)
            if resp == "a" or resp == "<":
                _page -= 1
                if _page < 1:
                    _page = max_page
            elif resp == "d" or resp == ">":
                _page += 1
                if _page > max_page:
                    _page = 1
            else:
                return

    return generator(page)


disp = command.mount(help_cmd)


@disp.on_execute()
async def help_exec(arp: Arparma):
    return help_cmd_handle(arp)


@disp.handle()
async def help_handle(arp: Arparma, session: Session):
    resp = help_cmd_handle(arp, True)
    if isinstance(resp, str):
        return await session.send(resp)
    msg = await session.prompt(next(resp), timeout=15)
    while msg:
        try:
            msg = await session.prompt(resp.send(msg.extract_plain_text().strip().lower()), timeout=15)
        except StopIteration:
            return
