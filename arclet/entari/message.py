from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence, MutableSequence
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar, Union, overload, Iterator
from typing_extensions import Self, SupportsIndex

from satori import select as satori_select
from satori.element import At, Custom, Element, Emoji, Link, Quote, Raw, Resource, Sharp, Style, Text, transform
from satori.model import MessageObject
from satori.parser import parse

T = TypeVar("T")
S = TypeVar("S")
TE = TypeVar("TE", bound=Element)
TE1 = TypeVar("TE1", bound=Element)

Fragment: TypeAlias = str | Element | Iterable[Element]
Visit: TypeAlias = Callable[[Element, S], T]
Render: TypeAlias = Callable[[dict[str, Any], list[Element], S], T]
SyncTransformer: TypeAlias = bool | Fragment | Render[S, bool | Fragment]
AsyncTransformer: TypeAlias = bool | Fragment | Render[S, Awaitable[bool | Fragment]]
SyncVisitor: TypeAlias = dict[str, SyncTransformer[S]] | Visit[S, bool | Fragment]
AsyncVisitor: TypeAlias = dict[str, AsyncTransformer[S]] | Visit[S, Awaitable[bool | Fragment]]

MessageContainer = Union[str, Element, Sequence["MessageContainer"], "MessageChain[Element]"]


class MessageChain(MutableSequence[TE]):
    """消息链, 被用于承载整个消息内容的数据结构, 包含有一有序列表, 包含有继承了 Element 的各式类实例."""

    @overload
    def __init__(self): ...

    @overload
    def __init__(self: MessageChain[Text], message: str): ...

    @overload
    def __init__(self, message: TE): ...

    @overload
    def __init__(self: MessageChain[TE1], message: TE1): ...

    @overload
    def __init__(self, message: Iterable[TE]): ...

    @overload
    def __init__(self: MessageChain[TE1], message: Iterable[TE1]): ...

    @overload
    def __init__(self: MessageChain[Text], message: Iterable[str]): ...

    @overload
    def __init__(self: MessageChain[Text | TE1], message: Iterable[str | TE1]): ...

    def __init__(
        self: MessageChain[Element],
        message: Iterable[str | TE] | str | TE | None = None,
    ):
        """从传入的序列(可以是元组 tuple, 也可以是列表 list) 创建消息链.
        Args:
            message (Iterable[str | TE] | str | TE): 包含且仅包含消息元素和字符串的序列
        Returns:
            MessageChain: 以传入的序列作为所承载消息的消息链
        """
        self.content: list[TE] = []
        if message:
            if isinstance(message, (str, Element)):
                self.__iadd__(message)
            else:
                for i in message:
                    self.__iadd__(i)

    def __str__(self) -> str:
        """获取以字符串形式表示的消息链, 且趋于通常你见到的样子.
        Returns:
            str: 以字符串形式表示的消息链
        """
        return "".join(str(elem) for elem in self.content)

    def __repr__(self) -> str:
        """获取以字符串形式表示的消息链的详细信息.
        Returns:
            str: 以字符串形式表示的消息链的详细信息
        """
        return "[" + ", ".join(repr(elem) for elem in self.content) + "]"

    @overload
    def __add__(self, other: str) -> MessageChain[TE | Text]: ...

    @overload
    def __add__(self, other: TE | Iterable[TE]) -> MessageChain[TE]: ...

    @overload
    def __add__(self, other: TE1 | Iterable[TE1]) -> MessageChain[TE | TE1]: ...

    def __add__(self, other: str | TE | TE1 | Iterable[TE | TE1]) -> MessageChain:
        """将另一个消息段或消息链添加到当前消息链.

        Args:
            other: 要添加的消息段或消息链

        Returns:
            添加后的消息链
        """
        result: MessageChain[Element] = self.fork()  # type: ignore
        if isinstance(other, str):
            if result.content and isinstance(text := result[-1], Text):
                result.content[-1] = Text(text.text + other)
            else:
                result.content.append(Text(other))
        elif isinstance(other, Element):
            if result.content and isinstance(text := result[-1], Text) and isinstance(other, Text):
                result.content[-1] = Text(text.text + other.text)
            else:
                result.content.append(other)
        elif isinstance(other, Iterable):
            for elem in other:
                result += elem
        else:
            raise TypeError(f"Unsupported type {type(other)!r}")
        return result

    @overload
    def __radd__(self, other: str) -> MessageChain[Text | TE]: ...

    @overload
    def __radd__(self, other: TE | Iterable[TE]) -> MessageChain[TE]: ...

    @overload
    def __radd__(self, other: TE1 | Iterable[TE1]) -> MessageChain[TE1 | TE]: ...

    def __radd__(self, other: str | TE1 | Iterable[TE1]) -> MessageChain:
        result = MessageChain(other)
        return result + self

    def __iadd__(self, other: str | TE | Iterable[TE]) -> Self:
        if isinstance(other, str):
            if self.content and isinstance(text := self[-1], Text):
                self.content[-1] = Text(text.text + other)  # type: ignore
            else:
                self.content.append(Text(other))  # type: ignore
        elif isinstance(other, Element):
            if self.content and (isinstance(text := self[-1], Text) and isinstance(other, Text)):
                self.content[-1] = Text(text.text + other.text)  # type: ignore
            else:
                self.content.append(other)
        elif other:
            for elem in other:
                self.__iadd__(elem)
        else:
            raise TypeError(f"Unsupported type {type(other)!r}")
        return self

    @overload
    def __getitem__(self, args: type[TE1], /) -> MessageChain[TE1]:
        """获取仅包含指定消息段类型的消息

        Args:
            args: 消息段类型

        Returns:
            所有类型为 `args` 的消息段
        """

    @overload
    def __getitem__(self, args: tuple[type[TE1], int], /) -> TE1:
        """索引指定类型的消息段

        Args:
            args: 消息段类型和索引

        Returns:
            类型为 `args[0]` 的消息段第 `args[1]` 个
        """

    @overload
    def __getitem__(self, args: tuple[type[TE1], slice], /) -> MessageChain[TE1]:
        """切片指定类型的消息段

        Args:
            args: 消息段类型和切片

        Returns:
            类型为 `args[0]` 的消息段切片 `args[1]`
        """

    @overload
    def __getitem__(self, args: int, /) -> TE:
        """索引消息段

        Args:
            args: 索引

        Returns:
            第 `args` 个消息段
        """

    @overload
    def __getitem__(self, args: slice, /) -> Self:
        """切片消息段

        Args:
            args: 切片

        Returns:
            消息切片 `args`
        """

    def __getitem__(
        self,
        args: type[TE1] | tuple[type[TE1], int] | tuple[type[TE1], slice] | int | slice,
    ) -> TE | TE1 | MessageChain[TE1] | Self:
        arg1, arg2 = args if isinstance(args, tuple) else (args, None)
        if isinstance(arg1, int) and arg2 is None:
            return self.content[arg1]
        if isinstance(arg1, slice) and arg2 is None:
            return MessageChain(self.content[arg1])  # type: ignore
        if TYPE_CHECKING:
            assert not isinstance(arg1, slice | int)
        if issubclass(arg1, Element) and arg2 is None:
            return MessageChain(elem for elem in self.content if isinstance(elem, arg1))  # type: ignore
        if issubclass(arg1, Element) and isinstance(arg2, int):
            return [elem for elem in self.content if isinstance(elem, arg1)][arg2]
        if issubclass(arg1, Element) and isinstance(arg2, slice):
            return MessageChain([elem for elem in self.content if isinstance(elem, arg1)][arg2])  # type: ignore
        raise ValueError("Incorrect arguments to slice")  # pragma: no cover

    def __setitem__(self, index: int, value: TE | str, /) -> None:
        if isinstance(value, str):
            value = Text(value)  # type: ignore
        self.content[index] = value  # type: ignore

    def __delitem__(self, index: int, /) -> None:
        del self.content[index]

    def __contains__(self, item: str | Element | type[Element] | Self | Sequence[str | Element]) -> bool:
        """判断消息链中是否含有特定的内容.

        Args:
            item (str | Element | type[Element] | Self | Sequence[str | Element]): 需判断内容.
        Returns:
            消息内是否存在给定消息段或给定类型的消息段
        """
        if isinstance(item, type):
            return not not next((elem for elem in self.content if isinstance(elem, item)), None)
        if isinstance(item, Element):
            return item in self.merge().content
        if isinstance(item, (MessageChain, Sequence)):
            return not not self.index_sub(item)

        raise ValueError(f"{item} is not an acceptable argument!")

    def merge(self, *, copy: bool = True) -> Self:
        """合并相邻的 Text 项, 选择返回一个新的消息链实例

        Returns:
            MessageChain: 得到的新的消息链实例, 里面不应存在有任何的相邻的 Text 元素.
        """

        result = []

        texts = []
        for i in self.content:
            if not isinstance(i, Text):
                if texts:
                    result.append(Text("".join(texts)))
                    texts.clear()  # 清空缓存
                result.append(i)
            else:
                texts.append(i.text)
        if texts:
            result.append(Text("".join(texts)))
            texts.clear()  # 清空缓存
        if copy:
            return self.__class__(result)
        self.content.clear()
        self.content.extend(result)
        return self

    has = __contains__

    def index(self, value: str | Element | type[Element], *args: SupportsIndex) -> int:
        """索引消息段

        Args:
            value: 消息段或者消息段类型
            args: start 与 end

        Returns:
            索引 index

        Raise:
            ValueError: 消息段不存在
        """
        if isinstance(value, type):
            first_elemment = next((elem for elem in self if isinstance(elem, value)), None)
            if first_elemment is None:
                raise ValueError(f"Element with type {value!r} is not in message")
            return self.content.index(first_elemment, *args)  # type: ignore
        if isinstance(value, str):
            value = Text(value)
        return self.content.index(value, *args)  # type: ignore

    def index_sub(self, sub: MessageChain | Sequence[str | Element]) -> list[int]:
        """判断消息链是否含有子链. 使用 KMP 算法.

        Args:
            sub (MessageChain | Sequence[str | Element]): 要判断的子链.

        Returns:
            List[int]: 所有找到的下标.
        """

        def unzip(seq: Sequence[str | Element]) -> list[str | Element]:
            res: list[str | Element] = []
            for e in seq:
                if isinstance(e, Text):
                    res.extend(e.text)
                elif isinstance(e, str):
                    res.extend(e)
                else:
                    res.append(e)
            return res

        pattern: list[str | Element] = unzip(sub.content) if isinstance(sub, MessageChain) else unzip(sub)

        match_target: list[str | Element] = unzip(self.content)

        if len(match_target) < len(pattern):
            return []

        fallback: list[int] = [0 for _ in pattern]
        current_fb: int = 0  # current fallback index
        for i in range(1, len(pattern)):
            while current_fb and pattern[i] != pattern[current_fb]:
                current_fb = fallback[current_fb - 1]
            if pattern[i] == pattern[current_fb]:
                current_fb += 1
            fallback[i] = current_fb

        match_index: list[int] = []
        ptr = 0
        for i, e in enumerate(match_target):
            while ptr and e != pattern[ptr]:
                ptr = fallback[ptr - 1]
            if e == pattern[ptr]:
                ptr += 1
            if ptr == len(pattern):
                match_index.append(i - ptr + 1)
                ptr = fallback[ptr - 1]
        return match_index

    def get(self, element_class: type[TE1], count: int | None = None) -> MessageChain[TE1]:
        """
        获取消息链中所有特定类型的消息元素

        Args:
            element_class (type[E]): 指定的消息元素的类型, 例如 "Text", "At", "Image" 等.
            count (int, optional): 至多获取的元素个数

        Returns:
            MessageChain[E]: 获取到的符合要求的所有消息元素; 另: 可能是空列表([]).
        """
        if count is None:
            return self[element_class]

        return MessageChain(elem for elem in self.content if isinstance(elem, element_class))[:count]  # type: ignore

    def get_one(self, element_class: type[TE1], index: int) -> TE1:
        """获取消息链中第 index + 1 个特定类型的消息元素
        Args:
            element_class (type[Element]): 指定的消息元素的类型, 例如 "Text", "At", "Image" 等.
            index (int): 索引, 从 0 开始数
        Returns:
            T: 消息链第 index + 1 个特定类型的消息元素
        """
        return self.get(element_class)[index]

    def get_first(self, element_class: type[TE1]) -> TE1:
        """获取消息链中第 1 个特定类型的消息元素
        Args:
            element_class (type[Element]): 指定的消息元素的类型, 例如 "Text", "At", "Image" 等.
        Returns:
            T: 消息链第 1 个特定类型的消息元素
        """
        return self.get(element_class)[0]

    def join(self, *chains: Self | Iterable[Self]) -> Self:
        """将多个消息链连接起来, 并在其中插入自身.

        Args:
            *chains (Iterable[MessageChain]): 要连接的消息链.

        Returns:
            MessageChain: 连接后的消息链, 已对文本进行合并.
        """
        result: list[TE] = []
        list_chains: list[MessageChain] = []
        for chain in chains:
            if isinstance(chain, MessageChain):
                list_chains.append(chain)
            else:
                list_chains.extend(chain)

        for chain in list_chains:
            if chain is not list_chains[0]:
                result.extend(deepcopy(self.content))
            result.extend(deepcopy(chain.content))
        return self.__class__(result).merge()

    def count(self, value: type[Element] | str | Element) -> int:
        """计算指定消息元素的个数

        Args:
            value (str | Element | type[Element]): 消息元素或消息元素类型

        Returns:
            int: 消息元素的个数
        """
        if isinstance(value, str):
            value = Text(value)
        return (
            len(self[value])  # type: ignore
            if isinstance(value, type)
            else self.content.count(value)  # type: ignore
        )

    def only(self, value: type[Element] | str | Element) -> bool:
        """检查消息中是否仅包含指定消息元素

        Args:
            value: 指定消息元素或消息元素类型

        Returns:
            bool: 是否仅包含指定消息元素
        """
        if isinstance(value, type):
            return all(isinstance(elem, value) for elem in self.content)
        if isinstance(value, str):
            value = Text(value)
        return all(elem == value for elem in self.content)

    def copy(self) -> Self:
        """深拷贝消息"""
        return deepcopy(self)

    def fork(self) -> Self:
        """浅拷贝消息"""
        new = self.__class__()
        new.content = self.content[:]
        return new

    def exclude(self, *types: type[Element]) -> Self:
        """将除了在给出的消息元素类型中符合的消息元素重新包装为一个新的消息链
        Args:
            *types (type[Element]): 将排除在外的消息元素类型
        Returns:
            MessageChain: 返回的消息链中不包含参数中给出的消息元素类型
        """
        return self.__class__([i for i in self.content if not isinstance(i, types)])

    def include(self, *types: type[Element]) -> Self:
        """将只在给出的消息元素类型中符合的消息元素重新包装为一个新的消息链
        Args:
            *types (type[Element]): 将只包含在内的消息元素类型
        Returns:
            MessageChain: 返回的消息链中只包含参数中给出的消息元素类型
        """
        return self.__class__([i for i in self.content if isinstance(i, types)])

    def extract_plain_text(self) -> str:
        """提取消息内纯文本消息"""

        return "".join(elem.text for elem in self if isinstance(elem, Text))

    def filter(self, predicate: Callable[[TE], bool]) -> MessageChain[TE]:
        """过滤消息

        Args:
            predicate: 过滤函数
        """
        return MessageChain(elem for elem in self.content if predicate(elem))

    def __iter__(self) -> Iterator[Element]:
        yield from self.content

    def __len__(self) -> int:
        return len(self.content)

    @overload
    def map(self, func: Callable[[TE], TE1]) -> MessageChain[TE1]: ...

    @overload
    def map(self, func: Callable[[TE], T]) -> list[T]: ...

    def map(self, func: Callable[[TE], TE1] | Callable[[TE], T]) -> MessageChain[TE1] | list[T]:
        result1 = []
        result2 = []
        for elem in self.content:
            result = func(elem)
            if isinstance(result, Element):
                result1.append(result)
            else:
                result2.append(result)
        if result1:
            return MessageChain(result1)
        return result2

    def select(self, cls: type[TE1]) -> MessageChain[TE1]:
        return MessageChain(satori_select(list(self), cls))

    @staticmethod
    def _visit_sync(elem: Element, rules: SyncVisitor[S], session: S = None):
        _type, data, children = elem.tag, elem._attrs, elem.children
        if isinstance(rules, Callable):
            return rules(elem, session)
        result = rules.get(_type, True)
        if not isinstance(result, bool | Element | Iterable):
            result = result(data, children, session)
        return result

    @staticmethod
    async def _visit_async(elem: Element, rules: AsyncVisitor[S], session: S = None):
        _type, data, children = elem.tag, elem._attrs, elem.children
        if isinstance(rules, Callable):
            return await rules(elem, session)
        result = rules.get(_type, True)
        if not isinstance(result, bool | Element | Iterable):
            result = await result(data, children, session)
        return result

    def transform(self, rules: SyncVisitor[S], session: S = None) -> MessageChain:
        """同步遍历消息元素并转换

        Args:
            rules: 转换规则
            session: 可能需要的会话信息, 由调用者传入

        Returns:
            转换后的消息
        """
        output = MessageChain()
        for elem in self.content:
            result = self._visit_sync(elem, rules, session)
            if result is True:
                children = MessageChain(elem.children)
                elem._children = list(children.transform(rules, session))
                output += elem
            elif result is not False:
                if isinstance(result, str | Element):
                    output += result
                else:
                    output.content.extend(result)
        return output

    async def transform_async(self, rules: AsyncVisitor[S], session: S = None) -> MessageChain:
        """异步遍历消息段并转换

        Args:
            rules: 转换规则
            session: 可能需要的会话信息, 由调用者传入

        Returns:
            转换后的消息
        """
        output = MessageChain()
        for elem in self.content:
            result = await self._visit_async(elem, rules, session)
            if result is True:
                children = MessageChain(elem.children)
                elem._children = list(await children.transform_async(rules, session))
                output += elem
            elif result is not False:
                if isinstance(result, str | Element):
                    output += result
                else:
                    output.extend(result)
        return output

    def split(self, pattern: str = " ") -> list[Self]:
        """和 `str.split` 差不多, 提供一个字符串, 然后返回分割结果.

        Args:
            pattern (str): 分隔符. 默认为单个空格.

        Returns:
            list[Self]: 分割结果, 行为和 `str.split` 差不多.
        """

        result: list[Self] = []
        tmp = []
        for seg in self.content:
            if isinstance(seg, Text):
                split_result = seg.text.split(pattern)
                for index, split_text in enumerate(split_result):
                    if tmp and index > 0:
                        result.append(self.__class__(tmp))
                        tmp = []
                    if split_text:
                        tmp.append(split_text)
            else:
                tmp.append(seg)
        if tmp:
            result.append(self.__class__(tmp))
            tmp = []
        return result

    def replace(
        self,
        old: str,
        new: str,
    ) -> Self:
        """替换消息中有关的文本

        Args:
            old (str): 要替换的字符串.
            new (str): 替换后的字符串.

        Returns:
            UniMessage: 修改后的消息链, 若未替换则原样返回.
        """
        result_list: list[TE] = []
        for seg in self.content:
            if isinstance(seg, Text):
                result_list.append(seg.__class__(seg.text.replace(old, new)))
            else:
                result_list.append(seg)
        return self.__class__(result_list)

    def startswith(self, string: str) -> bool:
        """判断消息链是否以给出的字符串开头

        Args:
            string (str): 字符串

        Returns:
            bool: 是否以给出的字符串开头
        """

        if not self.content or not isinstance(self.content[0], Text):
            return False
        return self.content[0].text.startswith(string)

    def endswith(self, string: str) -> bool:
        """判断消息链是否以给出的字符串结尾

        Args:
            string (str): 字符串

        Returns:
            bool: 是否以给出的字符串结尾
        """

        if not self.content or not isinstance(self.content[-1], Text):
            return False
        return self.content[-1].text.endswith(string)

    def append(self, element: Element | str) -> None:
        """
        向消息链最后追加单个元素

        Args:
            element (Element): 要添加的元素

        Returns:
            None
        """
        if isinstance(element, str):
            element = Text(element)
        self.content.append(element)  # type: ignore

    def insert(self, index: int, value: Element | str, /) -> None:
        if isinstance(value, str):
            value = Text(value)
        self.content.insert(index, value)  # type: ignore

    def extend(
        self,
        values: Iterable[Self | Element | list[Element | str]],
    ) -> None:
        """
        向消息链最后添加元素/元素列表/消息链

        Args:
            *values (MessageChain | Element | list[Element | str]): 要添加的元素/元素容器.

        Returns:
            MessageChain: copy = True 时返回副本, 否则返回自己的引用.
        """
        result = []
        for i in values:
            if isinstance(i, Element):
                result.append(i)
            elif isinstance(i, str):
                result.append(Text(i))
            elif isinstance(i, MessageChain):
                result.extend(i.content)
            else:
                for e in i:
                    if isinstance(e, str):
                        result.append(Text(e))
                    else:
                        result.append(e)
        self.content.extend(result)

    def empty(self) -> bool:
        """
        判断消息链是否为空，包括判断是否仅包含空字符串。

        Returns:
            bool: 判断结果。
        """

        return not bool(self.content and str(self))

    def pop(self, index: int = -1, /) -> TE:
        """移除并返回指定位置的元素，默认移除最后一个元素。

        Args:
            index (int, optional): 要移除的元素的索引，默认为 -1（最后一个元素）。

        Returns:
            TE: 被移除的元素。
        """
        return self.content.pop(index)  # type: ignore

    def removeprefix(self, prefix: str, *, copy: bool = True) -> Self:
        """移除消息链前缀.

        Args:
            prefix (str): 要移除的前缀.
            copy (bool, optional): 是否在副本上修改, 默认为 True.

        Returns:
            MessageChain: 修改后的消息链, 若未移除则原样返回.
        """
        elements = deepcopy(self.content) if copy else self.content
        if not elements:
            return self.copy() if copy else self
        elem = elements[0]
        if not isinstance(elem, Text):
            return self.copy() if copy else self
        if elem.text.startswith(prefix):
            elem.text = elem.text[len(prefix) :]
            if not elem.text:
                elements.pop(0)
        if copy:
            return self.__class__(elements)
        self.content.clear()
        self.content.extend(elements)
        return self

    def removesuffix(self, suffix: str, *, copy: bool = True) -> Self:
        """移除消息链后缀.

        Args:
            suffix (str): 要移除的后缀.
            copy (bool, optional): 是否在副本上修改, 默认为 True.

        Returns:
            MessageChain: 修改后的消息链, 若未移除则原样返回.
        """
        elements = deepcopy(self.content) if copy else self.content
        if not elements:
            return self.copy() if copy else self
        elem = elements[-1]
        if not isinstance(elem, Text):
            return self.copy() if copy else self
        if elem.text.endswith(suffix):
            elem.text = elem.text[: -len(suffix)]
            if not elem.text:
                elements.pop(-1)
        if copy:
            return self.__class__(elements)
        self.content.clear()
        self.content.extend(elements)
        return self

    def strip(self, *elements: str | type[Element] | Element, copy: bool = True) -> Self:
        return self.lstrip(*elements, copy=copy).rstrip(*elements, copy=copy)

    def lstrip(self, *elements: str | type[Element] | Element, copy: bool = True) -> Self:
        types = [i for i in elements if not isinstance(i, str)] or []
        chars = "".join([i for i in elements if isinstance(i, str)]) or None
        content = deepcopy(self.content) if copy else self.content
        if not content:
            return self.copy() if copy else self
        while content:
            elem = content[0]
            if elem in types or elem.__class__ in types:
                content.pop(0)
            elif isinstance(elem, Text):
                text = elem.text.lstrip(chars)
                if not text:
                    content.pop(0)
                    continue
                elem.text = text
                break
            else:
                break
        if copy:
            return self.__class__(content)
        self.content.clear()
        self.content.extend(content)
        return self

    def rstrip(self, *elements: str | type[Element] | Element, copy: bool = True) -> Self:
        types = [i for i in elements if not isinstance(i, str)] or []
        chars = "".join([i for i in elements if isinstance(i, str)]) or None
        content = deepcopy(self.content) if copy else self.content
        if not content:
            return self.copy() if copy else self
        while content:
            elem = content[-1]
            if elem in types or elem.__class__ in types:
                content.pop(-1)
            elif isinstance(elem, Text):
                text = elem.text.rstrip(chars)
                if not text:
                    content.pop(-1)
                    continue
                elem.text = text
                break
            else:
                break
        if copy:
            return self.__class__(content)
        self.content.clear()
        self.content.extend(content)
        return self

    def replace_chain(
        self,
        old: MessageChain | list[Element],
        new: MessageChain | list[Element],
    ) -> Self:
        """替换消息链中的一部分. (在副本上操作)

        Args:
            old (MessageChain): 要替换的消息链.
            new (MessageChain): 替换后的消息链.

        Returns:
            MessageChain: 修改后的消息链, 若未替换则原样返回.
        """
        if not isinstance(old, MessageChain):
            old = MessageChain(old)
        if not isinstance(new, MessageChain):
            new = MessageChain(new)
        index_list: list[int] = self.index_sub(old)

        def unzip(chain: MessageChain) -> list[str | Element]:
            unzipped: list[str | Element] = []
            for e in chain.content:
                if isinstance(e, Text):
                    unzipped.extend(e.text)
                else:
                    unzipped.append(e)
            return unzipped

        unzipped_new: list[str | Element] = unzip(new)
        unzipped_old: list[str | Element] = unzip(old)
        unzipped_self: list[str | Element] = unzip(self)
        unzipped_result: list[str | Element] = []
        last_end: int = 0
        for start in index_list:
            unzipped_result.extend(unzipped_self[last_end:start])
            last_end = start + len(unzipped_old)
            unzipped_result.extend(unzipped_new)
        unzipped_result.extend(unzipped_self[last_end:])

        # Merge result
        result_list: list[TE] = []
        char_stk: list[str] = []
        for v in unzipped_result:
            if isinstance(v, str):
                char_stk.append(v)
            else:
                result_list.append(Text("".join(char_stk)))  # type: ignore
                char_stk = []
                result_list.append(v)  # type: ignore
        if char_stk:
            result_list.append(Text("".join(char_stk)))  # type: ignore
        return self.__class__(result_list)

    def __bool__(self):
        return bool(self.content and str(self))

    def __eq__(self, value: object, /):
        if not isinstance(value, MessageChain):
            return False
        return value.content == self.content

    def display(self):
        texts = []
        for elem in self:
            if isinstance(elem, (Text, Style, At, Sharp, Link, Quote, Emoji, Raw)):
                texts.append(str(elem))
            elif isinstance(elem, Custom) and not elem.attributes():
                texts.append(str(elem))
            elif isinstance(elem, Resource) and not elem.src.startswith("data:"):
                texts.append(str(elem))
            else:
                texts.append(f"<{elem.__class__.__name__.lower()}/>")
        return "".join(texts)

    @staticmethod
    def of(text: str) -> MessageChain:
        return MessageChain(transform(parse(text)))


@dataclass
class Reply:
    quote: Quote
    origin: MessageObject
