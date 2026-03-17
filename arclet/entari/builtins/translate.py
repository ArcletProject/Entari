from arclet.entari import Entari, MessageChain, command, metadata
from arclet.entari.command import Match

API_URL = "https://simplytranslate.pussthecat.org/api/translate"

metadata(
    name="简易翻译",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="一个提供简易翻译功能的插件，使用第三方翻译API进行文本翻译。",
    readme="""
# 简易翻译

该插件使用第三方翻译API（[SimplyTranslate API](https://simplytranslate.pussthecat.org/)）
提供文本翻译功能。用户可以通过命令 `translate <text>` 来翻译指定的文本，并可选地指定目标语言。

## 使用

- 输入命令： `translate <...text>`，即可将 `<text>` 翻译成默认的目标语言（中文）。
- 输入命令： `translate --lang <target> <...text>`，即可将 `<text>` 翻译成指定的目标语言
`<target>`（例如：`en`、`zh-CN`、`ja` 等）。
""",
    config=None,
)


@command.command("translate <...content>").option("lang", "<target:str>")
async def send_joke(app: Entari, content: Match[MessageChain], target: str = "zh-CN"):
    params = {
        "engine": "google",
        "from": "auto",
        "to": target,
        "text": content.result.extract_plain_text(),
    }
    async with app.http.get(API_URL, params=params) as response:
        try:
            response.raise_for_status()
        except Exception as e:
            return repr(e)
        data = await response.json()
        return data["translated-text"]
