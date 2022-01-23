from typing import List, Iterable, Type, Union

from .element import MessageElement
from ..utilles import DataStructure, gen_subclass


class MessageChain(DataStructure):
    """
    即 "消息链", 用于承载整个消息内容的数据结构, 包含有一有序列表, 包含有继承了 MessageElement 的类实例.
    """

    __root__: List[MessageElement]

    @staticmethod
    def search_element(name: str):
        for i in gen_subclass(MessageElement):
            if i.__name__ == name:
                return i

    @staticmethod
    def build_chain(obj: List[Union[dict, MessageElement]]):
        elements = []
        for i in obj:
            if isinstance(i, MessageElement):
                elements.append(i)
            elif isinstance(i, dict) and "type" in i:
                elements.append(MessageChain.search_element(i["type"]).parse_obj(i))
        return elements

    @classmethod
    def parse_obj(cls: Type["MessageChain"], obj: List[Union[dict, MessageElement]]) -> "MessageChain":
        return cls(__root__=cls.build_chain(obj))  # 默认是不可变型

    def __init__(self, __root__: Iterable[MessageElement]):
        super().__init__(__root__=self.build_chain(list(__root__)))

    @classmethod
    def create(cls, *elements: Union[Iterable[MessageElement], MessageElement, str]) -> "MessageChain":
        element_list = []
        for ele in elements:
            if isinstance(ele, MessageElement):
                element_list.append(ele)
            elif isinstance(ele, str):
                from .element import Text
                element_list.append(Text(ele))
            else:
                element_list.extend(list(ele))
        return cls(__root__=element_list)

    def to_text(self) -> str:
        """获取以字符串形式表示的消息链, 且趋于通常你见到的样子.

        Returns:
            str: 以字符串形式表示的消息链
        """
        return "".join(i.to_text() for i in self.__root__)

    def to_serialization(self) -> str:
        """获取可序列化的字符串形式表示的消息链, 会存储所有的信息.

        Returns:
            str: 序列化的字符串形式的消息链
        """
        return "__root__: " + "".join(i.to_serialization()
                                      for i in self.replace_text('[', '[_').replace_text(']', '_]').__root__)

    @staticmethod
    def from_text(text: str) -> "MessageChain":
        from .element import Text
        return MessageChain([Text(text)])

    def only_text(self) -> str:
        """获取消息链中的纯文字部分
        """
        return "".join(i.to_text() if i else "" for i in self.findall("Plain"))

    def is_instance(self, element_type: Union[str, Type[MessageElement]]) -> bool:
        if isinstance(element_type, str):
            element_type = MessageChain.search_element(element_type)
        for i, v in enumerate(self.__root__):
            if v.__class__.__name__ in ("Source", "Quote"):
                continue
            if type(v) is not element_type:
                return False
        return True

    def findall(self, element_type: Union[str, Type[MessageElement]]) -> List[MessageElement]:
        """返回消息链内可能的所有指定元素"""
        if isinstance(element_type, str):
            element_type = MessageChain.search_element(element_type)
        return [i for i in self.__root__ if type(i) is element_type]

    def find(self, element_type: Union[str, Type[MessageElement]], index: int = 0) -> Union[bool, MessageElement]:
        """
        当消息链内有指定元素时返回该元素
        无则返回False

        Args:
            element_type : 指定的元素类型
            index: 位置索引, 默认为0
        """
        ele = self.findall(element_type)
        return False if not ele else ele[index]

    def has(self, element_type: Union[str, Type[MessageElement]]) -> bool:
        """
        当消息链内有指定元素时返回True
        无则返回False
        """
        ele = self.findall(element_type)
        return False if not ele else True

    def pop(self, index: int) -> MessageElement:
        return self.__root__.pop(index)

    def index(self, element_type: Union[str, Type[MessageElement]]) -> int:
        ele = self.find(element_type)
        if ele:
            return self.__root__.index(ele)
        else:
            raise ValueError(f"{element_type} is not in this MessageChain")

    def replace(self, element_type: Union[str, Type[MessageElement]],
                new_element: MessageElement, counts: int = None) -> "MessageChain":
        """替换消息链中的所有指定的消息元素类型为新的消息元素实例；不改变消息链本身

        Args:
            element_type : 要替换的元素的类型
            new_element: 新的消息元素实例
            counts: 替换的次数,不填写时默认为替换全部符合的元素
        Returns:
            MessageChain: 新的消息链
        """
        if isinstance(element_type, str):
            element_type = MessageChain.search_element(element_type)
        new_message = MessageChain(self.__root__)
        if not counts:
            for i, v in enumerate(self.__root__):
                if type(v) is element_type:
                    new_message.__root__[i] = new_element
        elif counts > 0:
            for i, v in enumerate(self.__root__):
                if type(v) is element_type:
                    counts -= 1
                    new_message.__root__[i] = new_element
                if counts == 0:
                    break
        return new_message

    def replace_text(self, old_text: str, new_text: str, counts: int = -1) -> "MessageChain":
        """替换消息链中可能含有的文本消息中的文本为指定文本；不改变消息链本身

        Args:
            old_text : 要替换的文本内容
            new_text: 新的文本内容
            counts: 替换的次数,不填写时默认为替换全部符合的元素
        Returns:
            MessageChain: 新的消息链
        """
        new_message = MessageChain(self.__root__)
        from arclet.cesloi.message.element import Plain
        for ele in new_message:
            if isinstance(ele, Plain):
                ele.text = ele.text.replace(old_text, new_text, counts)
        return new_message

    def remove(self, element_type: Union[str, Type[MessageElement]], counts: int = None):
        """删除消息链中的所有指定的消息元素类型

        Args:
            element_type : 要删除的元素的类型
            counts: 删除的次数,不填写时默认为删除全部符合的元素
        Returns:
            操作完成后的消息链本身
        """
        if isinstance(element_type, str):
            element_type = MessageChain.search_element(element_type)
        if not counts:
            self.__root__ = [i for i in self.__root__ if type(i) is not element_type]
        elif counts > 0:
            i = 0
            while counts:
                if type(self.__root__[i]) is element_type:
                    try:
                        self.__root__.remove(self.__root__[i])
                        counts -= 1
                        i -= 1
                    except ValueError:
                        break
                i += 1
        return self

    def only_save(self, element_type: Union[str, Type[MessageElement]]):
        """删除消息链中的所有非指定的消息元素类型

        Args:
            element_type : 要保留的元素的类型
        Returns:
            操作完成后的消息链本身
        """
        if isinstance(element_type, str):
            element_type = MessageChain.search_element(element_type)
        self.__root__ = [i for i in self.__root__ if type(i) is element_type]
        return self

    def insert(self, index: int, element: MessageElement):
        """在指定位置插入一个消息元素实例
        Args:
            index: 插入的位置
            element: 需要插入的消息元素
        Returns:
            操作完成后的消息链本身
        """
        self.__root__.insert(index, element)
        return self

    def append(self, element: MessageElement):
        """在消息链尾部增加一个消息元素实例

        Args:
            element: 需要插入的消息元素
        Returns:
            操作完成后的消息链本身
        """
        self.__root__.append(element)
        return self

    def extend(self, *elements: Union[MessageElement, List[MessageElement]]):
        element_list = []
        for ele in elements:
            if isinstance(ele, MessageElement):
                element_list.append(ele)
            else:
                element_list.extend(ele)
        self.__root__ += element_list
        return self

    def copy_self(self) -> "MessageChain":
        return MessageChain(self.__root__)

    def __add__(self, other) -> "MessageChain":
        if isinstance(other, MessageElement):
            self.__root__.append(other)
            return self
        elif isinstance(other, MessageChain):
            self.__root__.extend(i for i in other.__root__ if i.type != "Source")
            return self
        elif isinstance(other, List):
            self.__root__ += other
            return self

    def __repr__(self) -> str:
        return fr"MessageChain({repr(self.__root__)})"

    def __iter__(self) -> Iterable[MessageElement]:
        yield from self.__root__

    def __getitem__(self, index) -> MessageElement:
        return self.__root__[index]

    def __len__(self) -> int:
        return len(self.__root__)

    def __contains__(self, item: Union[Type[MessageElement], str]) -> bool:
        """
        是否包含特定元素类型/字符串
        """
        if isinstance(item, str):
            return item in self.find("Plain").to_text()
        else:
            return self.has(item)

    def to_sendable(self):
        return self.remove("Source").remove("Quote").remove("File")

    def startswith(self, string: str) -> bool:
        if not self.__root__:
            return False
        return self.to_text().startswith(string)

    def endswith(self, string: str) -> bool:
        if not self.__root__:
            return False
        return self.to_text().endswith(string)
