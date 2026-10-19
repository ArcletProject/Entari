# AGENTS.md

## Repository shape

- `arclet-entari` is a Python >=3.11 IM framework on the Satori protocol. The only published package is `arclet/entari/` (`[tool.pdm.build] includes = ["arclet"]`).
- Root-level scripts and fixtures are a manual test bed, not library code: `main*.py`, `exam*.py`, `sysmod_test.py`, `example_plugin*.py`, `example_plugins/`, `example*.yml`, `*.db`, `out_new.json`. Most are untracked. Do not move, format, or commit them unless asked.
- Version is dynamic, read from `arclet/entari/__init__.py:__version__`. The release workflow only publishes a `v*` tag whose version matches it.

## Commands and verification

- Lint: `ruff check ./arclet/entari`. CI (`.github/workflows/ruff.yml`) runs ruff; config only includes `arclet/**.py`, with line length 120.
- Format: `pdm run format` = `ruff check --select I --fix ./arclet/` -> `black ./arclet/` -> `ruff check ./arclet/`. `black` is not installed here; `ruff` is.
- Tests: there is no `tests/` directory. `pdm run test` (`pytest -v -n auto -W ignore ./tests/`) fails, and pytest is not a dev dependency. Verify changes with ruff plus a focused script/manual run; never claim tests passed.
- PDM/WSL trap: this checkout may be opened from WSL while `.pdm-python` points at a Windows venv (`D:/.../.venv/Scripts/python.exe`). If the venv layout does not match the host (e.g. WSL sees `Scripts/` instead of `bin/`), do not reuse it or let PDM recreate `.venv`—create a separate venv with a different directory name instead (`python -m venv .venv-linux` then `pdm use .venv-linux/bin/python`). Running `pdm run ...` against the mismatched venv **recreates `.venv`**, destroying the Windows environment.
- Line endings: the worktree is CRLF while the index is LF, so `git status` marks every tracked file modified. `git diff --ignore-space-at-eol` is empty. Review with that flag and never commit whitespace-only churn.

## Architecture map

- Entry point: `Entari` (`arclet/entari/core.py:304`) wraps Satori's `App`. `Entari.load(path)` / `Entari.from_config()` read `EntariConfig`; default lookup is `$ENTARI_CONFIG_FILE`, then `./.entari.json`, then `./entari.yml` (`config/file.py: EntariConfig.load`).
- Config uses a custom dataclass system, not pydantic: `BasicConfModel` + `model_field` (`config/models/default.py`), with optional backends in `config/models/{default,pyd,msgspec_}.py` behind `ConfigModelAction`. Use `config_model_validate/dump/keys/schema` from `arclet.entari.config` for conversions.
- Plugin system is the most intricate area: `plugin/module.py` (imports, AST scanning, code swap), `plugin/loader.py` (load/reload/rebind), `plugin/service.py` (dependency graph and state), `plugin/model.py` (`Plugin`, metadata, dispatchers), `plugin/swap.py` (hot-reload function replacement). Public API is re-exported from `plugin/__init__.py` and `arclet/entari/__init__.py`; keep both in sync when adding exports.
- Plugin name resolution (`config/file.py:_reload_plugins`, `plugin/module.py`): `::name` -> `arclet.entari.builtins.name`; `.name` -> core niches (`.record_message`, `.scheduler`, `.commands`); plain `name` -> `entari_plugin_name`; dotted names are used verbatim; `~name` disables, `?name` stores config without loading; `$files`, `$prelude`, `$prefix` are directives. `basic.external_dirs` are appended to `sys.path`.
- Builtins live in `arclet/entari/builtins/`. Other layers: `event/` (letoderea), `command/` (Alconna), `filter/`, `session.py`, `scheduler.py`, `config/`.
- Optional dependencies are guarded imports: YAML (`ruamel-yaml`), TOML (`tomlkit`), dotenv, watchfiles, croniter, rich, pydantic/msgspec. Keep new optional integrations import-guarded like `config/file.py`.
- `pyproject.toml` is the source of truth; update `pdm.lock` when dependencies change.

## Conventions

- Format at 120 columns, target py311. Public re-exports use explicit `from x import y as y`.
- Add comments only for non-obvious invariants; hot-reload code uses Chinese docstrings—match local style there.
