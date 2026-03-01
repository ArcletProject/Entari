from collections.abc import Mapping
import os
from pathlib import Path

from dotenv import dotenv_values


def load_env_with_environment(
    *,
    base_files: tuple[str, ...] = (".env", ".env.local"),
    environment_key: str = "environment",
    encoding: str = "utf-8",
    use_lowercase_keys: bool = False,
) -> dict[str, str]:
    """
    1) 读取 .env / .env.local，拿到 environment
    2) 若 environment 有值，则再读取 .env.{environment}
    3) 最终用系统环境变量覆盖 dotenv 文件

    返回：合并后的 key -> value（value 可能为 None）
    """

    def norm(k: str) -> str:
        return k.lower() if use_lowercase_keys else k.upper()

    def read_one(path: str) -> dict[str, str]:
        p = Path(path).expanduser()
        if not p.is_file():
            return {}
        raw = dotenv_values(p, encoding=encoding)
        return {norm(k): v for k, v in raw.items() if v is not None}

    def read_many(paths: tuple[str, ...]) -> dict[str, str]:
        out: dict[str, str] = {}
        for fp in paths:
            out.update(read_one(fp))
        return out

    # 1) 先读基础文件（后读覆盖先读）
    dotenv_vars = read_many(base_files)

    # 用“当前已读到的 dotenv + 系统环境变量”来解析 environment（系统环境变量优先）
    sys_env: Mapping[str, str] = {norm(k): v for k, v in os.environ.items()}
    merged_for_env = {**dotenv_vars, **sys_env}
    environment = merged_for_env.get(norm(environment_key))

    # 2) 再读 .env.{environment}
    if environment:
        env_suffix = environment.strip()
        if env_suffix:
            dotenv_vars.update(read_one(f".env.{env_suffix}"))

    # 3) 最终合并：系统环境变量覆盖 dotenv
    final = {**dotenv_vars, **sys_env}
    return final
