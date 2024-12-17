from __future__ import annotations

from collections.abc import Awaitable, Iterable, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, TypeVar, Union, overload
from typing_extensions import Self, SupportsIndex, TypeAlias

from satori import select as satori_select
from satori.element import At, Element, Link, Sharp, Style, Text

T = TypeVar("T")
TE = TypeVar("TE", bound=Element)
TE1 = TypeVar("TE1", bound=Element)

Fragment: TypeAlias = Union[Element, Iterable[Element]]
Visit: TypeAlias = Callable[[Element], T]
Render: TypeAlias = Callable[[dict[str, Any], list[Element]], T]
SyncTransformer: TypeAlias = Union[bool, Fragment, Render[Union[bool, Fragment]]]
AsyncTransformer: TypeAlias = Union[bool, Fragment, Render[Awaitable[Union[bool, Fragment]]]]
SyncVisitor: TypeAlias = Union[dict[str, SyncTransformer], Visit[Union[bool, Fragment]]]
AsyncVisitor: TypeAlias = Union[dict[str, AsyncTransformer], Visit[Awaitable[Union[bool, Fragment]]]]

MessageContainer = Union[str, Element, Sequence["MessageContainer"], "MessageChain[Element]"]


class MessageChain(list[TE]):
    """消息序列

    Args:
        message: 消息内容
    """

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
        super().__init__()
        if isinstance(message, str):
            self.__iadd__(Text(message))
        elif isinstance(message, Iterable):
            for i in message:
                self.__iadd__(Text(i) if isinstance(i, str) else i)
        elif isinstance(message, Element):
            self.__iadd__(message)

    def __str__(self) -> str:
        return "".join(str(elem) for elem in self)

    def __repr__(self) -> str:
        return "[" + ", ".join(repr(elem) for elem in self) + "]"

    @overload
    def __add__(self, other: str) -> MessageChain[TE | Text]: ...

    @overload
    def __add__(self, other: TE | Iterable[TE]) -> MessageChain[TE]: ...

    @overload
    def __add__(self, other: TE1 | Iterable[TE1]) -> MessageChain[TE | TE1]: ...

    def __add__(self, other: str | TE | TE1 | Iterable[TE | TE1]) -> MessageChain:
        result: MessageChain = self.copy()
        if isinstance(other, str):
            if result and isinstance(text := result[-1], Text):
                result[-1] = Text(text.text + other)
            else:
                result.append(Text(other))
        elif isinstance(other, Element):
            if result and isinstance(result[-1], Text) and isinstance(other, Text):
                result[-1] = Text(result[-1].text + other.text)
            else:
                result.append(other)
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
            if self and isinstance(text := self[-1], Text):
                list.__setitem__(self, -1, Text(text.text + other))
            else:
                self.append(Text(other))  # type: ignore
        elif isinstance(other, Element):
            if self and (isinstance(text := self[-1], Text) and isinstance(other, Text)):
                list.__setitem__(self, -1, Text(text.text + other.text))
            else:
                self.append(other)
        elif isinstance(other, Iterable):
            for elem in other:
                self.__iadd__(elem)
        else:
            raise TypeError(f"Unsupported type {type(other)!r}")
        return self

    @overload
    def __getitem__(self, args: type[TE1]) -> MessageChain[TE1]:
        """获取仅包含指定消息段类型的消息

        Args:
            args: 消息段类型

        Returns:
            所有类型为 `args` 的消息段
        """

    @overload
    def __getitem__(self, args: tuple[type[TE1], int]) -> TE1:
        """索引指定类型的消息段

        Args:
            args: 消息段类型和索引

        Returns:
            类型为 `args[0]` 的消息段第 `args[1]` 个
        """

    @overload
    def __getitem__(self, args: tuple[type[TE1], slice]) -> MessageChain[TE1]:
        """切片指定类型的消息段

        Args:
            args: 消息段类型和切片

        Returns:
            类型为 `args[0]` 的消息段切片 `args[1]`
        """

    @overload
    def __getitem__(self, args: int) -> TE:
        """索引消息段

        Args:
            args: 索引

        Returns:
            第 `args` 个消息段
        """

    @overload
    def __getitem__(self, args: slice) -> Self:
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
            return super().__getitem__(arg1)
        if isinstance(arg1, slice) and arg2 is None:
            return MessageChain(super().__getitem__(arg1))  # type: ignore
        if TYPE_CHECKING:
            assert not isinstance(arg1, (slice, int))
        if issubclass(arg1, Element) and arg2 is None:
            return MessageChain(elem for elem in self if isinstance(elem, arg1))  # type: ignore
        if issubclass(arg1, Element) and isinstance(arg2, int):
            return [elem for elem in self if isinstance(elem, arg1)][arg2]
        if issubclass(arg1, Element) and isinstance(arg2, slice):
            return MessageChain([elem for elem in self if isinstance(elem, arg1)][arg2])  # type: ignore
        raise ValueError("Incorrect arguments to slice")  # pragma: no cover

    def __contains__(self, value: str | Element | type[Element]) -> bool:
        """检查消息段是否存在

        Args:
            value: 消息段或消息段类型
        Returns:
            消息内是否存在给定消息段或给定类型的消息段
        """
        if isinstance(value, type):
            return bool(next((elem for elem in self if isinstance(elem, value)), None))
        if isinstance(value, str):
            value = Text(value)
        return super().__contains__(value)

    def has(self, value: str | Element | type[Element]) -> bool:
        return value in self

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
            return super().index(first_elemment, *args)
        if isinstance(value, str):
            value = Text(value)
        return super().index(value, *args)  # type: ignore

    def get(self, type_: type[TE], count: int | None = None) -> MessageChain[TE]:
        """获取指定类型的消息段

        Args:
            type_: 消息段类型
            count: 获取个数

        Returns:
            构建的新消息
        """
        if count is None:
            return self[type_]

        iterator, filtered = (elem for elem in self if isinstance(elem, type_)), MessageChain()
        for _ in range(count):
            elem = next(iterator, None)
            if elem is None:
                break
            filtered.append(elem)
        return filtered  # type: ignore

    def count(self, value: type[Element] | str | Element) -> int:
        """计算指定消息段的个数

        Args:
            value: 消息段或消息段类型

        Returns:
            个数
        """
        if isinstance(value, str):
            value = Text(value)
        return (
            len(self[value])  # type: ignore
            if isinstance(value, type)
            else super().count(value)  # type: ignore
        )

    def only(self, value: type[Element] | str | Element) -> bool:
        """检查消息中是否仅包含指定消息段

        Args:
            value: 指定消息段或消息段类型

        Returns:
            是否仅包含指定消息段
        """
        if isinstance(value, type):
            return all(isinstance(elem, value) for elem in self)
        if isinstance(value, str):
            value = Text(value)
        return all(elem == value for elem in self)

    def join(self, iterable: Iterable[TE1 | MessageChain[TE1]]) -> MessageChain[TE | TE1]:
        """将多个消息连接并将自身作为分割

        Args:
            iterable: 要连接的消息

        Returns:
            连接后的消息
        """
        ret = MessageChain()
        for index, msg in enumerate(iterable):
            if index != 0:
                ret.extend(self)
            if isinstance(msg, Element):
                ret.append(msg)
            else:
                ret.extend(msg.copy())
        return ret  # type: ignore

    def copy(self) -> MessageChain[TE]:
        """深拷贝消息"""
        return deepcopy(self)

    def include(self, *types: type[Element]) -> MessageChain:
        """过滤消息

        Args:
            types: 包含的消息段类型

        Returns:
            新构造的消息
        """
        return MessageChain(elem for elem in self if elem.__class__ in types)

    def exclude(self, *types: type[Element]) -> MessageChain:
        """过滤消息

        Args:
            types: 不包含的消息段类型

        Returns:
            新构造的消息
        """
        return MessageChain(elem for elem in self if elem.__class__ not in types)

    def extract_plain_text(self) -> str:
        """提取消息内纯文本消息"""

        return "".join(elem.text for elem in self if isinstance(elem, Text))

    def filter(self, predicate: Callable[[TE], bool]) -> MessageChain[TE]:
        """过滤消息

        Args:
            predicate: 过滤函数
        """
        return MessageChain(elem for elem in self if predicate(elem))

    @overload
    def map(self, func: Callable[[TE], TE1]) -> MessageChain[TE1]: ...

    @overload
    def map(self, func: Callable[[TE], T]) -> list[T]: ...

    def map(self, func: Callable[[TE], TE1] | Callable[[TE], T]) -> MessageChain[TE1] | list[T]:
        result1 = []
        result2 = []
        for elem in self:
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
    def _visit_sync(elem: Element, rules: SyncVisitor):
        _type, data, children = elem.tag, elem._attrs, elem.children
        if not isinstance(rules, dict):
            return rules(elem)
        result = rules.get(_type, True)
        if not isinstance(result, (bool, Element, Iterable)):
            result = result(data, children)
        return result

    @staticmethod
    async def _visit_async(elem: Element, rules: AsyncVisitor):
        _type, data, children = elem.tag, elem._attrs, elem.children
        if not isinstance(rules, dict):
            return await rules(elem)
        result = rules.get(_type, True)
        if not isinstance(result, (bool, Element, Iterable)):
            result = await result(data, children)
        return result

    def transform(self, rules: SyncVisitor) -> MessageChain:
        """同步遍历消息元素并转换

        Args:
            rules: 转换规则

        Returns:
            转换后的消息
        """
        output = MessageChain()
        for elem in self:
            result = self._visit_sync(elem, rules)
            if result is True:
                output += elem
            elif result is not False:
                if isinstance(result, Element):
                    output += result
                else:
                    output.extend(result)
        return output

    async def transform_async(self, rules: AsyncVisitor) -> MessageChain:
        """异步遍历消息段并转换

        Args:
            rules: 转换规则

        Returns:
            转换后的消息
        """
        output = MessageChain()
        for elem in self:
            result = await self._visit_async(elem, rules)
            if result is True:
                output += elem
            elif result is not False:
                if isinstance(result, Element):
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
        for seg in self:
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
        for seg in self:
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

        if not self or not isinstance(self[0], Text):
            return False
        return list.__getitem__(self, 0).text.startswith(string)

    def endswith(self, string: str) -> bool:
        """判断消息链是否以给出的字符串结尾

        Args:
            string (str): 字符串

        Returns:
            bool: 是否以给出的字符串结尾
        """

        if not self or not isinstance(self[-1], Text):
            return False
        return list.__getitem__(self, -1).text.endswith(string)

    def removeprefix(self, prefix: str) -> Self:
        """移除消息链前缀.

        Args:
            prefix (str): 要移除的前缀.

        Returns:
            UniMessage: 修改后的消息链.
        """
        copy = list.copy(self)
        if not copy:
            return self.__class__(copy)
        seg = copy[0]
        if not isinstance(seg, Text):
            return self.__class__(copy)
        if seg.text.startswith(prefix):
            seg = seg.__class__(seg.text[len(prefix) :])
            if not seg.text:
                copy.pop(0)
            else:
                copy[0] = seg
        return self.__class__(copy)

    def removesuffix(self, suffix: str) -> Self:
        """移除消息链后缀.

        Args:
            suffix (str): 要移除的后缀.

        Returns:
            UniMessage: 修改后的消息链.
        """
        copy = list.copy(self)
        if not copy:
            return self.__class__(copy)
        seg = copy[-1]
        if not isinstance(seg, Text):
            return self.__class__(copy)
        if seg.text.endswith(suffix):
            seg = seg.__class__(seg.text[: -len(suffix)])
            if not seg.text:
                copy.pop(-1)
            else:
                copy[-1] = seg
        return self.__class__(copy)

    def strip(self, *segments: str | Element | type[Element]) -> Self:
        return self.lstrip(*segments).rstrip(*segments)

    def lstrip(self, *segments: str | Element | type[Element]) -> Self:
        types = [i for i in segments if not isinstance(i, str)] or []
        chars = "".join([i for i in segments if isinstance(i, str)]) or None
        copy = list.copy(self)
        if not copy:
            return self.__class__(copy)
        while copy:
            seg = copy[0]
            if seg in types or seg.__class__ in types:
                copy.pop(0)
            elif isinstance(seg, Text):
                seg = seg.__class__(seg.text.lstrip(chars))
                if not seg.text:
                    copy.pop(0)
                    continue
                else:
                    copy[0] = seg
                break
            else:
                break
        return self.__class__(copy)

    def rstrip(self, *segments: str | Element | type[Element]) -> Self:
        types = [i for i in segments if not isinstance(i, str)] or []
        chars = "".join([i for i in segments if isinstance(i, str)]) or None
        copy = list.copy(self)
        if not copy:
            return self.__class__(copy)
        while copy:
            seg = copy[-1]
            if seg in types or seg.__class__ in types:
                copy.pop(-1)
            elif isinstance(seg, Text):
                seg = seg.__class__(seg.text.rstrip(chars))
                if not seg.text:
                    copy.pop(-1)
                    continue
                else:
                    copy[-1] = seg
                break
            else:
                break
        return self.__class__(copy)

    def display(self):
        return "".join(
            str(elem) if isinstance(elem, (Text, Style, At, Sharp, Link)) else elem.__class__.__name__ for elem in self
        )
