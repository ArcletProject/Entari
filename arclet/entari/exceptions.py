class RegisterNotInPluginError(Exception):
    def __init__(self, func, mod, pid):
        self.msg = f"""\
Handler `{func.__qualname__}` from {func.__module__!r} should define in the same module as the plugin: {mod.__name__!r}.

Please choose one of the following solutions before import it:
 * add {func.__module__!r} to your config file.
 * write the comment after the import statement line: `# entari: plugin`
 * append `load_plugin({func.__module__!r})` before the import statement.
 * call `requires({func.__module__!r})` before the import statement.
 * write the comment after the import statement line: `# entari: package`
 * call `package({func.__module__!r})` to let it marked as a sub-plugin of `{pid}`.\
"""
        try:
            from rich.console import Console
            from rich.panel import Panel

            panel = Panel(
                f"""\
[cyan]Handler [bright_yellow]`{func.__qualname__}`[/] from [blue]{func.__module__!r}\
[/] should define [u bright_white]in the same module[/] as the plugin: [blue]{mod.__name__!r}[/].

Please choose one of the following solutions [u bright_white]before import it[/]:
[magenta] *[/] add [bright_green]{func.__module__!r}[/] to your config file.
[magenta] *[/] write the comment after the import statement line: [white]`# entari: plugin`[/]
[magenta] *[/] append [bright_yellow]`load_plugin({func.__module__!r})`[/] before the import statement.
[magenta] *[/] call [bright_yellow]`requires({func.__module__!r})`[/] before the import statement.
[magenta] *[/] write the comment after the import statement line: [white]`# entari: package`[/]
[magenta] *[/] call [bright_yellow]`package({func.__module__!r})`[/] to let it marked as a sub-plugin of `{pid}`.\
""",
                title="Notice",
                style="bold red",
                expand=True,
            )
            csl = Console(force_terminal=True)
            with csl.capture() as capture:
                csl.print(panel)
            self.msg = capture.get()
        except ImportError:
            pass


class StaticPluginDispatchError(Exception):
    pass


class ReusablePluginError(Exception):
    pass
