from random import Random

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


class VerifyCodeChecker(type):
    def __init__(cls, name, bases, dic):
        if "verify_code" not in cls.__annotations__ or cls.__annotations__["verify_code"] != str:
            raise ValueError
        if not cls.__dict__.get("verify_code"):
            raise ValueError
        super().__init__(name, bases, dic)
