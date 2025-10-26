import random

from ..config import config


def generate_token() -> str:
    return f"{config.b}{random.randint(config.a, 999999)}"
