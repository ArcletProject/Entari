<div align="center"> 
  
# Edoves

  > _las su dres rin romilu, nann sune ri edar neru._
  
</div>

## 简介
[![Licence](https://img.shields.io/github/license/ArcletProject/Edoves)](https://github.com/ArcletProject/Edoves/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-edoves)](https://pypi.org/project/arclet-edoves)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-edoves)](https://www.python.org/)
![Edoves](https://img.shields.io/badge/Arclet-Edoves-2564c2.svg)

Edoves 是 `Arclet Project` 基于同项目下的 `Cesloi` 的 **第二代** 框架实现, 采取了模块化设计, 最大程度上简化了交互操作

**该框架目前处于快速迭代状态, API 可能会发生 _剧烈_ 变化, 建议根据changelog选择合适的版本**

### [文档 <----](https://arcletproject.github.io/docs/edoves/tutorial)

## 安装
```
pip install --upgrade arclet-edoves
```

## 特性
+ 主要部分
    - [x] `InteractiveObject`: 对`Unity3d`中`GameObject`的简易模仿
        - [x] `Monomer`: 代表逻辑关系的IO
          - [ ] `PremissonGroup` 存储权限相关信息
        - [x] `Module`: 负责处理事件的IO
            - [x] `ServerDocker`: 负责网络会话交互
            - [x] `Commander`: 基于 `Arclet Alconna` 的指令触发系统
        - [x] `DataParser`: 负责低层级的数据处理
    - [x] `Component`: IO的主要属性, 负责实际的数据管理与事件响应
    - [x] `Medium`: 传输事件信息的载体
    - [x] `Protocol`: 作为数据源与IO的转接层, 负责数据解析与`Medium`的调度
    - [x] `Scene`: 对IO统一的生命周期管理, 是多账号功能的实现
    - [x] `Server`: 对IO的管理, 包括`Scene`的管理
    - [ ] `Premission`: 权限管理
+ 杂项
    - [x] `NetworkClient`: 对网络端的抽象处理
    - [x] `Filter`: 对事件内容的限制操作

+ 实现支持
    - [x] `Edoves for mirai-api-http` : 对 [ `mirai-api-http` ](https://github.com/project-mirai/mirai-api-http) 的支持.
    - [ ] `Edoves for OneBot` : 对  [ `OneBot` ](https://github.com/botuniverse/onebot) 的协议实现.
    - [ ] `Edoves for go-cqhttp` : 对 [ `go-cqhttp` ](https://github.com/Mrs4s/go-cqhttp) 的扩展 API 支持.

## 样例

main.py:
```python
from arclet.edoves.mah.module import MessageModule
from arclet.edoves.mah import MAHConfig
from arclet.edoves.builtin.medium import Message
from arclet.edoves.builtin.event.message import MessageReceived
from arclet.edoves.builtin.client import AiohttpClient
from arclet.edoves.main import Edoves


async def test_message_reaction(message: Message):
    if message.content.startswith("Hello World"):
        await message.set("I received 'Hello World'!").send()


app = Edoves(
    configs={
        "MAH-default": (
            MAHConfig,
            {"verify_token": "INITKEYWylsVdbr", "port": "9080", "client": AiohttpClient, "account": 3542928737}
        )
    }
)
with app["MAH-default"].context() as scene:
    scene.require_module(MessageModule).add_handler(MessageReceived, test_message_reaction)
app.run()
```

## 相关项目

> 这些项目都非常优秀, 我相信你听说过他们

+ [`Graia Framework`](https://github.com/GraiaProject)
  - [`Avilla`](https://github.com/GraiaProject/Avilla): `Graia Project` 的 "下一代" 框架实现
  - [ `Ariadne` ](https://github.com/GraiaProject/Ariadne): 继承了 `Graia Project` 中 `Application` 并进行了许多改进后产生的作品
+ [ `Mamoe Technologies` ](https://github.com/mamoe):
    - [ `mirai` ](https://github.com/mamoe/mirai)
    - [ `mirai-api-http` ](https://github.com/project-mirai/mirai-api-http)

## 开源协议

Edoves 及其拓展 使用 MIT 作为开源协议.

但如果你若引用到了使用具有传染性开源协议（如 GPL/AGPL/LGPL 等）的项目, 请遵循相关规则.