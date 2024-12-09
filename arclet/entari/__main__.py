from importlib.util import find_spec
from pathlib import Path

from arclet.alconna import Alconna, Args, CommandMeta, Option, Subcommand, command_manager
from arclet.alconna.tools.formatter import RichConsoleFormatter

from arclet.entari import Entari

alc = Alconna(
    "entari",
    Subcommand("new", help_text="新建一个 Entari 配置文件"),
    Option("-c|--config", Args["path/", str], help_text="指定配置文件路径"),
    meta=CommandMeta(
        "Entari App Launcher",
    ),
    formatter_type=RichConsoleFormatter,
)


JSON_TEMPLATE = """\
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
  "plugins": {
    "~record_message": true,
    "::auto_reload": {
        "watch_dirs": ["."]
    },
    "::echo": true,
    "::inspect": true
  }
}
"""


YAML_TEMPLATE = """\
basic:
  network:
    - type: websocket
      host: "127.0.0.1"
      port: 5140
      path: "satori"
  ignore_self_message: true
  log_level: "info"
  prefix: ["/"]
plugins:
  ~record_message: true
  ::auto_reload:
    watch_dirs: ["."]
  ::echo: true
  ::inspect: true
"""


def main():
    res = alc()
    if not res.matched:
        return
    command_manager.delete(alc)
    if res.find("new"):
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
            with _path.open("w", encoding="utf-8") as f:
                f.write(JSON_TEMPLATE)
            print(f"Config file created at {_path}")
            return
        if _path.suffix in (".yaml", ".yml"):
            with _path.open("w", encoding="utf-8") as f:
                f.write(YAML_TEMPLATE)
            print(f"Config file created at {_path}")
            return
        print(f"Unsupported file extension: {_path.suffix}")
        return
    entari = Entari.load(res.query[str]("config.path", None))
    entari.run()
