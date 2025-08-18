from importlib.util import find_spec
from pathlib import Path
import re
import shutil
import subprocess
import sys

from arclet.alconna import Alconna, Args, CommandMeta, MultiVar, Option, Subcommand, command_manager
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.alconna.tools.formatter import RichConsoleFormatter
from colorama.ansi import Fore, Style

from arclet.entari import Entari, __version__
from arclet.entari.config import EntariConfig

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
        Subcommand("current", help_text="查看当前配置文件"),
        help_text="配置文件操作",
    ),
    Subcommand(
        "new",
        Args["name/?", str],
        Option("-S|--static", help_text="是否为静态插件"),
        Option("-A|--application", help_text="是否为应用插件"),
        Option("-f|--file", help_text="是否为单文件插件"),
        Option("-D|--disabled", help_text="是否插件初始禁用"),
        Option("-O|--optional", help_text="是否仅存储插件配置而不加载插件"),
        Option("-p|--priority", Args["num/", int], help_text="插件加载优先级"),
        help_text="新建一个 Entari 插件",
    ),
    Subcommand(
        "add",
        Args["name/?", str],
        Option("-D|--disabled", help_text="是否插件初始禁用"),
        Option("-O|--optional", help_text="是否仅存储插件配置而不加载插件"),
        Option("-p|--priority", Args["num/", int], help_text="插件加载优先级"),
        help_text="添加一个 Entari 插件到配置文件中",
    ),
    Subcommand("remove", Args["name/?", str], help_text="从配置文件中移除一个 Entari 插件"),
    Subcommand("run", help_text="运行 Entari"),
    Subcommand("gen_main", help_text="生成一个 Entari 主程序文件"),
    Option("-c|--config", Args["path/", str], help_text="指定配置文件路径", dest="cfg_path"),
    Option("-V|--version", help_text="查看版本信息"),
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

PLUGIN_DEFAULT_TEMPLATE = """\
from arclet.entari import metadata

metadata(
    name="{name}",
    author={author},
    version="{version}",
    description="{description}",
)
"""


PLUGIN_STATIC_TEMPLATE = """\
from arclet.entari import declare_static, metadata

metadata(
    name="{name}",
    author={author},
    version="{version}",
    description="{description}",
)
declare_static()
"""

PLUGIN_PROJECT_TEMPLATE = """\
[project]
name = "{name}"
version = "{version}"
description = "{description}"
author = [
    {author}
]
dependencies = [
    "arclet.entari >= {entari_version}",
]
requires-python = {python_requirement}
readme = "README.md"
license = {license}
"""

README_TEMPLATE = """\
# {name}
{description}
"""

MAIN_SCRIPT = """\
from arclet.entari import Entari

app = Entari.load({path})
app.run()
"""

PYTHON_VERSION = sys.version_info[:2]


def get_user_email_from_git() -> tuple[str, str]:
    """Get username and email from git config.
    Return empty if not configured or git is not found.
    """
    git = shutil.which("git")
    if not git:
        return "", ""
    try:
        username = subprocess.check_output([git, "config", "user.name"], text=True, encoding="utf-8").strip()
    except subprocess.CalledProcessError:
        username = ""
    try:
        email = subprocess.check_output([git, "config", "user.email"], text=True, encoding="utf-8").strip()
    except subprocess.CalledProcessError:
        email = ""
    return username, email


def validate_project_name(name: str) -> bool:
    """Check if the project name is valid or not"""

    pattern = r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$"
    return re.fullmatch(pattern, name, flags=re.IGNORECASE) is not None


def sanitize_project_name(name: str) -> str:
    """Sanitize the project name and remove all illegal characters"""
    pattern = r"[^a-zA-Z0-9\-_\.]+"
    result = re.sub(pattern, "-", name)
    result = re.sub(r"^[\._-]|[\._-]$", "", result)
    if not result:
        raise ValueError(f"Invalid project name: {name}")
    return result


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
    if res.find("version"):
        print(f"Entari {Fore.CYAN}{Style.BRIGHT}{__version__}{Fore.RESET}")
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
    if res.find("new"):
        is_application = res.find("new.application")
        if not is_application:
            ans = input(f"Is this an plugin project? {Fore.MAGENTA}(Y/n): {Fore.RESET}").strip().lower()
            is_application = ans in {"no", "false", "f", "0", "n", "n/a", "none", "nope", "nah"}
        name = res.query[str]("new.name")
        if not name:
            name = input(f"Plugin name: {Fore.RESET}").strip()
        if not validate_project_name(name):
            print(f"{Fore.RED}Invalid plugin name: {name!r} {Fore.RESET}")
            return
        proj_name = sanitize_project_name(name).replace(".", "-").replace("_", "-")
        if not proj_name.lower().startswith("entari-plugin-") and not is_application:
            print(f"{Fore.RED}Plugin will be corrected to 'entari-plugin-{proj_name}' automatically.")
            print(
                f"{Fore.YELLOW}If you want to keep the name, please use option {Fore.MAGENTA}-A|--application.{Fore.RESET}"  # noqa: E501
            )
            proj_name = f"entari-plugin-{proj_name}"
        file_name = proj_name.replace("-", "_")
        version = input(f"Plugin version {Fore.MAGENTA}(0.1.0){Fore.RESET}: ").strip() or "0.1.0"
        description = input(f"Plugin description: {Fore.RESET}").strip()
        git_user, git_email = get_user_email_from_git()
        author = input(f"Plugin author name {Fore.MAGENTA}({git_user}){Fore.RESET}: ").strip() or git_user
        email = input(f"Plugin author email {Fore.MAGENTA}({git_email}){Fore.RESET}: ").strip() or git_email
        if not is_application:
            default_python_requires = f">={PYTHON_VERSION[0]}.{PYTHON_VERSION[1]}"
            python_requires = (
                input(
                    f"Python requires('*' to allow any) {Fore.MAGENTA}({default_python_requires}){Fore.RESET}: "
                ).strip()
                or default_python_requires
            )
            licence = input(f"License(SPDX name) {Fore.MAGENTA}(MIT){Fore.RESET}: ").strip() or "MIT"
        else:
            python_requires = ""
            licence = ""
        is_file = res.find("new.file")
        if not is_file:
            ans = input(f"Is this a single file plugin? {Fore.MAGENTA}(Y/n): {Fore.RESET}").strip().lower()
            is_file = ans in {"yes", "true", "t", "1", "y", "yea", "yeah", "yep", "sure", "ok", "okay", ""}
        is_static = res.find("new.static")
        if not is_static:
            ans = input(f"Is this a disposable plugin? {Fore.MAGENTA}(Y/n): {Fore.RESET}").strip().lower()
            is_static = ans in {"no", "false", "f", "0", "n", "n/a", "none", "nope", "nah"}
        if proj_name.startswith("entari-plugin-") and find_spec(file_name):
            print(f"{Fore.RED}'{proj_name}' already installed, please use another name.{Fore.RESET}")
            return
        path = Path.cwd() / ("plugins" if is_application else "src")
        path.mkdir(parents=True, exist_ok=True)
        if is_file:
            path = path.joinpath(f"{file_name}.py")
        else:
            path = path.joinpath(file_name, "__init__.py")
            path.parent.mkdir(exist_ok=True)
        with path.open("w+", encoding="utf-8") as f:
            t = PLUGIN_STATIC_TEMPLATE if is_static else PLUGIN_DEFAULT_TEMPLATE
            f.write(
                t.format(
                    name=proj_name,
                    author=f'[{{"name": "{author}", "email": "{email}"}}]',
                    version=version,
                    description=description,
                )
            )
        if not is_application:
            toml_path = Path.cwd() / "pyproject.toml"
            if not toml_path.exists():
                with toml_path.open("w+", encoding="utf-8") as f:
                    f.write(
                        PLUGIN_PROJECT_TEMPLATE.format(
                            name=proj_name,
                            version=version,
                            description=description,
                            author=f'{{"name" = "{author}", "email" = "{email}"}}',
                            entari_version=__version__,
                            python_requirement=f'"{python_requires}"',
                            license=f'{{"text" = "{licence}"}}',
                        )
                    )
            readme_path = Path.cwd() / "README.md"
            if not readme_path.exists():
                with readme_path.open("w+", encoding="utf-8") as f:
                    f.write(README_TEMPLATE.format(name=proj_name, description=description))
        cfg = EntariConfig.load(res.query[str]("cfg_path.path", None))
        if file_name in cfg.plugin:
            return
        if f"entari_plugin_{file_name}" in cfg.plugin:
            return
        if file_name.removeprefix("entari_plugin_") in cfg.plugin:
            return
        cfg.plugin[file_name] = {}
        if res.find("new.disabled"):
            cfg.plugin[file_name]["$disable"] = True
        if res.find("new.optional"):
            cfg.plugin[file_name]["$optional"] = True
        if res.find("new.priority"):
            cfg.plugin[file_name]["priority"] = res.query[int]("new.priority.num", 16)
        if is_application:
            cfg._origin_data["basic"].setdefault("external_dirs", []).append("plugins")
        cfg.save()
        print(f"{Fore.GREEN}Plugin created at {path}.{Fore.RESET}")
        return
    if res.find("add"):
        name = res.query[str]("add.name")
        if not name:
            print(f"{Fore.BLUE}Please specify a plugin name:")
            name = input(f"{Fore.RESET}>>> ").strip()
        cfg = EntariConfig.load(res.query[str]("cfg_path.path", None))
        name_ = name.replace("::", "arclet.entari.builtins.")
        if find_spec(name_):
            pass
        elif not name_.count(".") and find_spec(f"entari_plugin_{name_}"):
            pass
        else:
            print(
                f"{Fore.BLUE}{name_!r}{Fore.RED} not found.\nYou should installed it, or run {Fore.GREEN}`entari new {name_}`{Fore.RESET}"  # noqa: E501
            )
            return
        cfg.plugin[name] = {}
        if res.find("add.disabled"):
            cfg.plugin[name]["$disable"] = True
        if res.find("add.optional"):
            cfg.plugin[name]["$optional"] = True
        if res.find("add.priority"):
            cfg.plugin[name]["priority"] = res.query[int]("add.priority.num", 16)
        cfg.save()
        return
    if res.find("remove"):
        name = res.query[str]("add.name")
        if not name:
            print(f"{Fore.BLUE}Please specify a plugin name:")
            name = input(f"{Fore.RESET}>>> ").strip()
        cfg = EntariConfig.load(res.query[str]("cfg_path.path", None))
        cfg.plugin.pop(name, None)
        cfg.save()
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
