from random import Random

UNKNOWN = 17156595
UNDEFINED = 30502508
MIRAI_API_HTTP_DEFAULT = 23330442
ONEBOT_DEFAULT = 18207135
GO_CQHTTP_DEFAULT = 1731916


def generate_identifier(extremal_data_source_id: str):
    tls = [(c, i) for i, c in enumerate(extremal_data_source_id.upper().replace('-', '_'))]
    rand = Random()
    rand.seed(sum([(ord(c)//(i + 1) + i + 1) for c, i in tls]))
    rand.shuffle(tls)
    h = 0
    for i, c in enumerate(tls):
        h = 0x1f * (h + c[1] - i) + ord(c[0]) ^ h
    return h % 0x1ffffff

