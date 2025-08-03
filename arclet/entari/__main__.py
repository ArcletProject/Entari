import asyncio
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from signal import SIGINT, SIGTERM, raise_signal
from typing import Union

from arclet.alconna import Alconna, Args, CommandMeta, MultiVar, Option, Subcommand, command_manager
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.alconna.tools.formatter import RichConsoleFormatter
from arclet.letoderea import publish
from colorama.ansi import Fore
from satori import Api
from satori.client import Account, ApiInfo
from satori.event import Event
from satori.exception import ActionFailed
from satori.model import Channel, ChannelType, Guild, Login, LoginStatus, MessageObject, User

from arclet.entari import Entari, listen
from arclet.entari.config import EntariConfig
from arclet.entari.event.base import MessageCreatedEvent
from arclet.entari.event.lifespan import Ready
from arclet.entari.event.plugin import PluginLoadedFailed
from arclet.entari.session import EntariProtocol

alc = Alconna(
    "entari",
    Subcommand(
        "config",
        Subcommand(
            "new",
            Option("-d|--dev", help_text="是否生成开发用配置文件"),
            Option("-P|--plugins", Args["names/", MultiVar(str)], help_text="指定增加哪些插件"),
            help_text="新建一个 Entari 配置文件",
        ),
        Option("current", help_text="查看当前配置文件"),
        help_text="配置文件操作",
    ),
    Subcommand(
        "plugin",
        Args["name/?", str],
        Subcommand(
            "new",
            Option("-S|--static", help_text="是否为静态插件"),
            Option("-A|--application", help_text="是否为应用插件"),
            Option("-f|--file", help_text="是否为单文件插件"),
            help_text="新建一个 Entari 插件",
        ),
        Subcommand("test", help_text="测试 Entari 插件是否可用"),
        help_text="插件操作",
    ),
    Subcommand("run", help_text="运行 Entari"),
    Subcommand("gen_main", help_text="生成一个 Entari 主程序文件"),
    Option("-c|--config", Args["path/", str], help_text="指定配置文件路径", dest="cfg_path"),
    meta=CommandMeta(
        "Entari App Launcher",
    ),
    formatter_type=RichConsoleFormatter,
)


class TestProtocol(EntariProtocol):

    async def call_api(
        self, action: Union[str, Api], params: Union[dict, None] = None, multipart: bool = False, method: str = "POST"
    ):
        if action is Api.MESSAGE_CREATE and params:
            print(params["content"])
            return [MessageObject(str(id(params["content"])), params["content"]).dump()]
        if action is Api.GUILD_GET:
            return Guild("@console", "Console").dump()
        if action is Api.GUILD_LIST:
            return {"data": [Guild("@console", "Console").dump()]}
        if action is Api.CHANNEL_GET:
            return Channel("@console", ChannelType.DIRECT, "Console").dump()
        if action is Api.CHANNEL_LIST:
            return {"data": [Channel("@console", ChannelType.DIRECT, "Console").dump()]}
        if action is Api.USER_GET:
            return User("@user", "User").dump()
        if action is Api.FRIEND_LIST:
            return {"data": [User("@user", "User").dump()]}
        raise ActionFailed("Unsupported action")


JSON_BASIC_TEMPLATE = """\
{
  "basic": {
    "network": [
      {
        "type": "websocket",
        "host": "127.0.0.1",
        "port": 5140,
        "path": "satori"
      }
    ],
    "ignore_self_message": true,
    "log_level": "info",
    "prefix": ["/"]
  },
"""

JSON_PLUGIN_BLANK_TEMPLATE = """\
  "plugins": {{
{plugins}
  }}
}}
"""

JSON_PLUGIN_COMMON_TEMPLATE = """\
  "plugins": {
    ".record_message": {},
    "::echo": {},
    "::inspect": {}
  }
}
"""

JSON_PLUGIN_DEV_TEMPLATE = """\
  "plugins": {
    "$prelude": [
      "::auto_reload"
    ],
    ".record_message": {
      "record_send": true,
    },
    "::help": {},
    "::echo": {},
    "::inspect": {},
    "::auto_reload": {
      "watch_config": true
    }
  }
}
"""


YAML_BASIC_TEMPLATE = """\
basic:
  network:
    - type: websocket
      host: "127.0.0.1"
      port: 5140
      path: "satori"
  ignore_self_message: true
  log_level: "info"
  prefix: ["/"]
"""

YAML_PLUGIN_BLANK_TEMPLATE = """\
plugins:
{plugins}
"""


YAML_PLUGIN_COMMON_TEMPLATE = """\
plugins:
  .record_message: {}
  ::echo: {}
  ::inspect: {}
"""

YAML_PLUGIN_DEV_TEMPLATE = """\
plugins:
  $prelude:
    - ::auto_reload
  .record_message:
    record_send: true
  ::echo: {}
  ::help: {}
  ::inspect: {}
  ::auto_reload:
    watch_config: true
"""

PLUGIN_DEFAULT_TEMPLATE = """\
from arclet.entari import metadata

metadata(name="{name}")
"""


PLUGIN_STATIC_TEMPLATE = """\
from arclet.entari import declare_static, metadata

metadata(name="{name}")
declare_static()
"""

MAIN_SCRIPT = """\
from arclet.entari import Entari

app = Entari.load({path})
app.run()
"""


def check_env(file: Path):
    env = Path.cwd() / ".env"
    if env.exists():
        lines = env.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith("ENTARI_CONFIG_FILE"):
                lines[i] = f"ENTARI_CONFIG_FILE='{file.resolve().as_posix()}'"
                with env.open("w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                break
    else:
        with env.open("w+", encoding="utf-8") as f:
            f.write(f"\nENTARI_CONFIG_FILE='{file.resolve().as_posix()}'")


def main():
    res = alc()
    if not res.matched or res.non_component:
        if not res.error_info:
            print(alc.get_help())
        elif not isinstance(res.error_info, SpecialOptionTriggered):
            print(res.error_info)
        return
    if res.find("config"):
        if res.find("config.new"):
            is_dev = res.find("config.new.dev")
            names = res.query[tuple[str, ...]]("config.new.plugins.names", ())
            if (path := res.query[str]("cfg_path.path", None)) is None:
                if find_spec("ruamel.yaml"):
                    _path = Path.cwd() / "entari.yml"
                else:
                    _path = Path.cwd() / ".entari.json"
            else:
                _path = Path(path)
            if _path.exists():
                print(f"{_path} already exists")
                return
            if _path.suffix.startswith(".json"):
                if names:
                    PT = JSON_PLUGIN_BLANK_TEMPLATE.format(plugins=",\n".join(f'    "{name}": {{}}' for name in names))
                elif is_dev:
                    PT = JSON_PLUGIN_DEV_TEMPLATE
                else:
                    PT = JSON_PLUGIN_COMMON_TEMPLATE

                with _path.open("w", encoding="utf-8") as f:
                    f.write(JSON_BASIC_TEMPLATE + PT)
                check_env(_path)
                print(f"Config file created at {_path}")
                return
            if _path.suffix in (".yaml", ".yml"):
                if names:
                    PT = YAML_PLUGIN_BLANK_TEMPLATE.format(plugins="\n".join(f"  {name}: {{}}" for name in names))
                elif is_dev:
                    PT = YAML_PLUGIN_DEV_TEMPLATE
                else:
                    PT = YAML_PLUGIN_COMMON_TEMPLATE

                with _path.open("w", encoding="utf-8") as f:
                    f.write(YAML_BASIC_TEMPLATE + PT)
                check_env(_path)
                print(f"Config file created at {_path}")
                return
            print(f"Unsupported file extension: {_path.suffix}")
            return
        if res.find("config.current"):
            cfg = EntariConfig.load()
            print(f"Current config file:\n{Fore.BLUE}{cfg.path.resolve()!s}")
            return
    if res.find("plugin"):
        name = res.query[str]("plugin.name")
        if res.find("plugin.new"):
            if not name:
                print(f"{Fore.BLUE}Please specify a plugin name:")
                name = input(f"{Fore.RESET}>>> ").strip()
            is_application = res.find("plugin.new.application")
            if not name.startswith("entari_plugin_") and not is_application:
                print(f"{Fore.RED}Plugin will be corrected to 'entari_plugin_{name}' automatically.")
                print(f"{Fore.RESET}If you want to keep the name, please use option {Fore.MAGENTA}-A|--application.")
                name = f"entari_plugin_{name}"
            is_file = res.find("plugin.new.file")
            is_static = res.find("plugin.new.static")
            if name.startswith("entari_plugin_") and find_spec(name):
                print(f"'{name}' already installed, please use another name.")
                return
            path = Path.cwd() / ("plugins" if is_application else "src")
            path.mkdir(parents=True, exist_ok=True)
            if is_file:
                path = path.joinpath(f"{name}.py")
            else:
                path = path.joinpath(name, "__init__.py")
                path.parent.mkdir(exist_ok=True)
            with path.open("w+", encoding="utf-8") as f:
                f.write((PLUGIN_STATIC_TEMPLATE if is_static else PLUGIN_DEFAULT_TEMPLATE).format(name=name))
            cfg = EntariConfig.load(res.query[str]("cfg_path.path", None))
            if name in cfg.plugin:
                return
            if f"entari_plugin_{name}" in cfg.plugin:
                return
            if name.removeprefix("entari_plugin_") in cfg.plugin:
                return
            cfg.plugin[name] = {}
            if is_application:
                cfg._basic_data.setdefault("external_dirs", []).append("plugins")
            cfg.save()
            return
        if res.find("plugin.test"):
            if not name:
                print(f"{Fore.BLUE}Please specify a plugin name:")
                name = input(f"{Fore.RESET}>>> ").strip()
            cfg = EntariConfig.load(res.query[str]("cfg_path.path", None))
            cfg.basic.network = []
            for k in list(cfg.plugin.keys()):
                if k.startswith("."):
                    continue
                if k in {name, f"entari_plugin_{name}", name.removeprefix("entari_plugin_")}:
                    continue
                del cfg.plugin[k]
            if not (
                name in cfg.plugin
                or f"entari_plugin_{name}" in cfg.plugin
                or name.removeprefix("entari_plugin_") in cfg.plugin
            ):
                cfg.plugin[name] = {}
            entari = Entari.from_config(cfg)

            @listen(PluginLoadedFailed)
            async def _():
                print(f"{Fore.RED}Plugin {Fore.YELLOW}{name}{Fore.RED} failed to load, please check the plugin.")
                raise_signal(SIGTERM)

            @listen(Ready)
            async def _():
                print(f"{Fore.BLUE}Please send a message to test the plugin (you can type the element tag):")
                text = input(f"{Fore.RESET}>>> ").strip()
                lg = Login(
                    0, LoginStatus.ONLINE, "test", "@console", User("@bot", "Bot", is_bot=True), ["message.guild"]
                )
                ev = MessageCreatedEvent(
                    Account(lg, ApiInfo(), [], protocol_cls=TestProtocol),
                    Event(
                        "message-created",
                        datetime.now(),
                        lg,
                        user=User("@user", "User"),
                        channel=Channel("@console", ChannelType.DIRECT, "Console"),
                        guild=Guild("@console", "Console"),
                        message=MessageObject(str(id(text)), text),
                    ),
                )
                await publish(ev)
                await asyncio.sleep(1)
                raise_signal(SIGINT)

            entari.run()
            return
    if res.find("run"):
        command_manager.delete(alc)
        entari = Entari.load(res.query[str]("cfg_path.path", None))
        entari.run()
        return
    if res.find("gen_main"):
        file = Path.cwd() / "main.py"
        path = res.query[str]("cfg_path.path", "")
        with file.open("w+", encoding="utf-8") as f:
            f.write(MAIN_SCRIPT.format(path=f'"{path}"'))
        print(f"Main script generated at {file}")
        return
    print(alc.formatter.format_node(res.origin))
