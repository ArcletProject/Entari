from arclet.alconna import Alconna, Args, CommandMeta, Option, command_manager
from arclet.alconna.tools.formatter import RichConsoleFormatter

from arclet.entari import Entari

alc = Alconna(
    "entari",
    Option("-c|--config", Args["path", str], help_text="指定配置文件路径"),
    meta=CommandMeta(
        "Entari App Launcher",
    ),
    formatter_type=RichConsoleFormatter,
)


def main():
    res = alc()
    if not res.matched:
        return
    command_manager.delete(alc)
    entari = Entari.load(res.query[str]("config.path", None))
    entari.run()
