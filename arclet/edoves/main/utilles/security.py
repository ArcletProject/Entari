from random import Random
import re

UNKNOWN = "17156595"
UNDEFINED = "30502508"
EDOVES_DEFAULT = "80503"
MIRAI_API_HTTP_DEFAULT = "23330442"
ONEBOT_DEFAULT = "18207135"
GO_CQHTTP_DEFAULT = "1731916"


def generate_identifier(extremal_data_source_id: str):
    tls = [(c, i) for i, c in enumerate(extremal_data_source_id.upper().replace('-', '_'))]
    rand = Random()
    rand.seed(sum([(ord(c) // (i + 1) + i + 1) for c, i in tls]))
    rand.shuffle(tls)
    h = 0
    for i, c in enumerate(tls):
        h = 0x1f * (h + c[1] - i) + ord(c[0]) ^ h
    return str(h % 0x1ffffff)


class VerifyCodeChecker:
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        if "verify_code" not in cls.__annotations__:
            raise ValueError("You must define 'verify_code' in your class")
        if not cls.__dict__.get("verify_code") or not isinstance(cls.__dict__.get("verify_code"), str):
            raise ValueError("verify_code must be a string")
        return super().__new__(cls)


def check_name(name: str):
    if name == "":
        raise ValueError("Scene的名字不能为空")
    if re.match(r"^[-`~?/.,<>;\':\"|!@#$%^&*()_+=\[\]}{]+.*$", name):
        raise ValueError("该Scene的名字含有非法字符")
