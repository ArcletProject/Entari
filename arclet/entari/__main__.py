from importlib.util import find_spec
from pathlib import Path

from arclet.alconna import Alconna, Args, CommandMeta, MultiVar, Option, Subcommand, command_manager
from arclet.alconna.tools.formatter import RichConsoleFormatter

from arclet.entari import Entari

alc = Alconna(
    "entari",
    Subcommand(
        "new",
        Option("-d|--dev", help_text="是否生成开发用配置文件"),
        Option("-P|--plugins", Args["names/", MultiVar(str)], help_text="指定增加哪些插件"),
        help_text="新建一个 Entari 配置文件",
    ),
    Subcommand("run", help_text="运行 Entari"),
    Option("-c|--config", Args["path/", str], help_text="指定配置文件路径"),
    meta=CommandMeta(
        "Entari App Launcher",
    ),
    formatter_type=RichConsoleFormatter,
)


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
    if (not res.matched or res.non_component) and not res.error_info:
        print(alc.get_help())
        return
    if res.find("new"):
        is_dev = res.find("new.dev")
        names = res.query[tuple[str, ...]]("new.plugins.names", ())
        if (path := res.query[str]("config.path", None)) is None:
            if find_spec("yaml"):
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
    if res.find("run"):
        command_manager.delete(alc)
        entari = Entari.load(res.query[str]("config.path", None))
        entari.run()
