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


@command.on("norris")
async def send_joke(app: Entari):
    async with app.http.get(API_URL) as response:
        try:
            response.raise_for_status()
        except Exception as e:
            return repr(e)
        data = await response.json()
        joke = data.get("value", "No joke found.")
        return joke
