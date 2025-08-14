from arclet.alconna import Alconna, Args, CommandMeta, Field, Option, namespace
from tarina import lang

from arclet.entari import Session, metadata
from arclet.entari.command import Match, mount

metadata(
    name="lang",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="i18n配置相关功能",
    config=None,
)

with namespace("builtin/lang") as ns:
    ns.disable_builtin_options = {"shortcut", "completion"}

    cmd = mount(
        Alconna(
            "lang",
            Option("list", Args["name?", str], help_text="查看支持的语言列表"),
            Option("switch", Args["locale?", str, Field(completion=lambda: "比如 zh-CN")], help_text="切换语言"),
            meta=CommandMeta("i18n配置相关功能", compact=True),
        ),
    )


@cmd.assign("list")
async def _(name: Match[str], sess: Session):
    try:
        locales = lang.locales_in(name.result) if name.available else lang.locales
    except KeyError:
        await sess.send(f"未能找到 {name.result} 所属的 i18n 目录")
    else:
        await sess.send("支持的语言列表:" + "\n" + "\n".join(f" * {locale}" for locale in locales))


@cmd.assign("switch")
async def _(locale: Match[str], sess: Session):
    if not locale.available:
        resp = await sess.prompt("缺少语言参数，请输入：", timeout=30)
        if resp is None:
            await sess.send("等待语言参数输入超时。")
            return
        _locale = str(resp)
    else:
        _locale = locale.result
    try:
        lang.select(_locale)
    except ValueError as e:
        await sess.send(f"无法切换到语言 {_locale}，请检查语言是否存在。错误信息: {e}")
        return
    else:
        await sess.send(f"切换语言成功: '{_locale}'。")
        return
