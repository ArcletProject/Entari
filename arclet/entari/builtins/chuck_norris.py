from arclet.entari import Entari, command, metadata

metadata(
    name="查克诺里斯笑话",
    author=[{"name": "RF-Tar-Railt", "email": "rf_tar_railt@qq.com"}],
    description="一个提供随机查克诺里斯笑话的插件。",
    readme="""
# 查克诺里斯笑话

该插件提供一个命令 `norris`，当用户输入该命令时，插件会从 [Chuck Norris Jokes API](https://api.chucknorris.io/)
获取一个随机的查克诺里斯笑话并发送给用户。

## 使用

直接输入命令： `norris`，即可获得一个随机的查克诺里斯笑话。
""",
    config=None,
)

API_URL = "https://api.chucknorris.io/jokes/random"


@command.command("norris {count?}", "随机的查克诺里斯笑话")
async def send_joke(app: Entari, count: int = 1):
    """获取随机的查克诺里斯笑话"""

    async def fetch_joke():
        async with app.http.get(API_URL) as response:
            try:
                response.raise_for_status()
            except Exception as e:
                return repr(e)
            data = await response.json()
            return data.get("value", "No joke found.")

    if count < 1:
        return "笑话数量必须大于等于 1。"
    jokes = []
    for _ in range(count):
        joke = await fetch_joke()
        jokes.append(joke)
    return "\n".join(jokes)
